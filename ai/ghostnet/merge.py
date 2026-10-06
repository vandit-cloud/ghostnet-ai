"""One object, one detection: merging sightings from overlapping tiles.

`survey._offsets` overlaps neighbouring tiles (25 % by default) so that a seam
never cuts an object in half with no tile seeing the whole of it. The price is
that an object in an overlap is scored twice, from two frames, and comes back
as two detections with two ids and nearly the same position. This module folds
those back into one.

Why SURVEY coordinates, not frame coordinates or lat/lon
--------------------------------------------------------
A box is in its own frame's pixels, so two sightings of one object have
unrelated boxes until each is shifted by its tile's offset: row += first ping,
column += first waterfall column. In those survey pixels the same object scored
from two tiles lands on the same pixels -- the image under it is identical --
so the match can be tight. Lat/lon would do too, but it is only present when
the navigation is, and its error (3 m GPS + heading lever arm) is larger than
the objects; pixels are exact and always available.

The rule
--------
Two detections are one object when ALL of these hold:

  * they come from DIFFERENT frames, and a survivor absorbs at most one
    sighting from any frame. Two boxes in one frame already went through the
    detector's own NMS; overruling it here would be a second, unmeasured NMS
    wearing a seam-merge label.
  * the same contract class, and the same detector class where the payload
    names one ("detector class: wreck" in notes). A wreck and an aircraft
    both report as `debris`; one tile calling it a wreck and the other an
    aircraft is a disagreement for a reviewer, not a duplicate to hide.
  * in survey pixels: IoU >= seam_merge_iou (0.30), OR the smaller box lies
    >= seam_merge_containment (0.60) inside the larger (a tile that clips the
    object at its border sees a smaller box inside the whole one, and their
    IoU can be tiny), OR their centres are <= seam_merge_centre_px (24 px)
    apart.

The survivor is the highest calibrated confidence; a tie goes to the sighting
further from its own tile's border, because that one had context on every
side.

Masks: the survivor keeps its own, unchanged
--------------------------------------------
Unioning two U-Net polygons was considered and rejected. A mask is in its
frame's pixels (contract 1.3.0), and the union of two sightings can extend past
the survivor's frame -- a polygon with coordinates outside the image it is
drawn on, which the viewer cannot show and the contract does not allow. The
overlap is 160 px, so a net short enough to fit is seen whole by one tile and
that tile's mask is already the full outline; a longer net is fragmented by the
U-Net's connected components regardless of tiling. So the best-scoring
sighting's mask is kept as it was predicted, and the absorbed ones are named.

Suppression is never silent
---------------------------
Every merge is written down twice: the survivor's `evidence_summary.notes`
names each sighting it absorbed (id, frame, confidence), and the frame that
lost a detection gets a warning naming where it went. The contract has no
field for this, and `notes` is free text by design, so no schema change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from .config import SETTINGS, Settings

#: How `survey._iter_tiles` names a tile: survey, first ping row, first column.
#: The backend persists only the id, so this format is also how it recovers a
#: frame's survey offsets without a schema change -- keep the two in step.
FRAME_ID_FORMAT = "%s__p%06d__x%05d"
_FRAME_ID_RE = re.compile(r"__p(\d+)__x(\d+)$")
_DETECTOR_CLASS_RE = re.compile(r"detector class:\s*([A-Za-z_]+)")


def frame_id_for(survey_id: str, ping_offset: int, col_offset: int) -> str:
    return FRAME_ID_FORMAT % (survey_id, ping_offset, col_offset)


def frame_offsets(frame_id: str | None) -> tuple[int, int] | None:
    """(first ping row, first column) of a tile from its id, or None.

    None for anything the tiler did not name -- an uploaded PNG, say -- which
    is exactly right: frames that were never cut from one waterfall cannot
    overlap, so there is nothing to merge them with.
    """
    m = _FRAME_ID_RE.search(frame_id or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def detector_class(detection: dict[str, Any]) -> str:
    """The detector's own class, parsed from notes; the contract class if absent.

    infer.detect writes "detector class: X" only when X differs from the
    contract class, so absence means they agree.
    """
    notes = ((detection.get("evidence_summary") or {}).get("notes")) or ""
    m = _DETECTOR_CLASS_RE.search(notes)
    return (m.group(1) if m else str(detection.get("class", ""))).lower()


Box = tuple[float, float, float, float]  # x0, y0, x1, y1 in survey pixels


def survey_box(bbox: Iterable[float], ping_offset: int, col_offset: int) -> Box:
    x, y, w, h = (float(v) for v in bbox)
    return (col_offset + x, ping_offset + y, col_offset + x + w, ping_offset + y + h)


def same_place(a: Box, b: Box, settings: Settings = SETTINGS) -> bool:
    """Whether two survey-pixel boxes are close enough to be one object."""
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    if inter > 0:
        union = area_a + area_b - inter
        if union > 0 and inter / union >= settings.seam_merge_iou:
            return True
        smaller = min(area_a, area_b)
        if smaller > 0 and inter / smaller >= settings.seam_merge_containment:
            return True
    ca = ((a[0] + a[2]) / 2.0, (a[1] + a[3]) / 2.0)
    cb = ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)
    return ((ca[0] - cb[0]) ** 2 + (ca[1] - cb[1]) ** 2) ** 0.5 <= settings.seam_merge_centre_px


@dataclass
class Sighting:
    """One detection, placed in survey pixels. `ref` is whatever the caller
    needs to find it again (an index pair here, a database row in the app)."""

    ref: Any
    frame_key: Any
    cls: str
    det_cls: str
    score: float
    box: Box
    #: Distance from the box to its own tile's nearest border, in pixels.
    margin: float = 0.0
    absorbed: list["Sighting"] = field(default_factory=list)

    @property
    def rank(self) -> tuple[float, float]:
        return (self.score, self.margin)


def is_duplicate(a: Sighting, b: Sighting, settings: Settings = SETTINGS) -> bool:
    """Whether `a` is another sighting of survivor `b`.

    Frame-distinct in BOTH directions: `a` must not share a frame with `b`
    nor with anything `b` already absorbed. Without the second half, three
    overlapping pot boxes the detector kept side by side in one tile were all
    folded into one survivor from the neighbouring tile (ghost_gear fixture,
    50 % overlap) -- a second NMS on boxes the detector had already chosen to
    keep apart. A survivor absorbs at most one sighting per frame; the rest
    stay as their own detections, exactly as the old tiling showed them.
    """
    if a.frame_key == b.frame_key or any(a.frame_key == x.frame_key for x in b.absorbed):
        return False
    if a.cls != b.cls or a.det_cls != b.det_cls:
        return False
    return same_place(a.box, b.box, settings)


def border_margin(bbox: Iterable[float], frame_w: int, frame_h: int) -> float:
    x, y, w, h = (float(v) for v in bbox)
    return max(0.0, min(x, y, frame_w - (x + w), frame_h - (y + h)))


class SeamIndex:
    """Survivors seen so far, searchable by position. Used both in one batch
    (`cluster`) and incrementally, by a consumer that persists detections
    frame by frame and must decide each one as it arrives (the web backend).

    Bucketed by survey row so a long line does not compare every detection
    with every other: an object can only duplicate one within a tile's reach.
    """

    def __init__(self, settings: Settings = SETTINGS, bucket_rows: int = 640) -> None:
        self.settings = settings
        self._bucket = max(1, int(bucket_rows))
        self._rows: dict[int, list[Sighting]] = {}

    def _span(self, box: Box) -> range:
        slack = self.settings.seam_merge_centre_px
        return range(int((box[1] - slack) // self._bucket), int((box[3] + slack) // self._bucket) + 1)

    def find(self, s: Sighting) -> Sighting | None:
        """The best-ranked survivor `s` duplicates, or None."""
        best = None
        seen: set[int] = set()
        for b in self._span(s.box):
            for other in self._rows.get(b, ()):
                if id(other) in seen:
                    continue
                seen.add(id(other))
                if is_duplicate(s, other, self.settings) and (best is None or other.rank > best.rank):
                    best = other
        return best

    def add(self, s: Sighting) -> None:
        for b in self._span(s.box):
            self._rows.setdefault(b, []).append(s)

    def remove(self, s: Sighting) -> None:
        for b in self._span(s.box):
            bucket = self._rows.get(b, [])
            if s in bucket:
                bucket.remove(s)

    def offer(self, s: Sighting) -> tuple[Sighting, Sighting | None]:
        """Add a sighting, merging it with a duplicate already held.

        Returns (survivor, loser): loser is None when `s` was new. When `s`
        outranks the held one, `s` takes its place and inherits what the old
        survivor had already absorbed, so the record of merges is never lost
        to a reordering.
        """
        held = self.find(s)
        if held is None:
            self.add(s)
            return s, None
        if s.rank > held.rank:
            self.remove(held)
            s.absorbed.extend(held.absorbed)
            held.absorbed = []
            s.absorbed.append(held)
            self.add(s)
            return s, held
        held.absorbed.append(s)
        return held, s


def cluster(sightings: list[Sighting], settings: Settings = SETTINGS) -> list[Sighting]:
    """Greedy, best first: each sighting joins the best survivor it duplicates,
    or becomes one. Returns the survivors, each with `absorbed` filled."""
    index = SeamIndex(settings)
    survivors = []
    for s in sorted(sightings, key=lambda s: s.rank, reverse=True):
        held = index.find(s)
        if held is None:
            index.add(s)
            survivors.append(s)
        else:
            held.absorbed.append(s)
    return survivors


def describe(s: Sighting, frame_id: str, detection_id: str) -> str:
    return "%s (frame %s, conf %.3f)" % (detection_id, frame_id, s.score)


def merge_survey_frames(
    frames: list[dict[str, Any]],
    offsets: list[tuple[int, int]],
    settings: Settings = SETTINGS,
    tile: int = 640,
) -> int:
    """Merge seam duplicates across a survey's frame payloads, IN PLACE.

    `offsets[i]` is (ping_offset, col_offset) of `frames[i]`. Absorbed
    detections are removed from their frame; the survivor's notes and the
    loser's frame warnings say what happened. Returns how many were merged.
    """
    sightings = []
    for fi, (payload, (row0, col0)) in enumerate(zip(frames, offsets)):
        for di, d in enumerate(payload.get("detections", [])):
            sightings.append(
                Sighting(
                    ref=(fi, di),
                    frame_key=fi,
                    cls=str(d.get("class")),
                    det_cls=detector_class(d),
                    score=float(d.get("calibrated_confidence") or 0.0),
                    box=survey_box(d["bbox"], row0, col0),
                    margin=border_margin(d["bbox"], tile, tile),
                )
            )
    survivors = cluster(sightings, settings)

    drop: dict[int, set[int]] = {}
    merged = 0
    for s in survivors:
        if not s.absorbed:
            continue
        sfi, sdi = s.ref
        keep = frames[sfi]["detections"][sdi]
        names = []
        for a in s.absorbed:
            afi, adi = a.ref
            gone = frames[afi]["detections"][adi]
            names.append(describe(a, frames[afi]["frame_id"], gone["detection_id"]))
            drop.setdefault(afi, set()).add(adi)
            frames[afi].setdefault("warnings", []).append(
                "detection %s merged into %s on overlapping frame %s: the same object "
                "seen from two tiles" % (gone["detection_id"], keep["detection_id"], frames[sfi]["frame_id"])
            )
        merged += len(s.absorbed)
        ev = keep.setdefault("evidence_summary", {})
        note = "merged %d seam duplicate(s) from overlapping tiles: %s" % (len(names), "; ".join(names))
        ev["notes"] = (ev.get("notes") + " | " + note) if ev.get("notes") else note

    for fi, idx in drop.items():
        frames[fi]["detections"] = [d for i, d in enumerate(frames[fi]["detections"]) if i not in idx]
    return merged
