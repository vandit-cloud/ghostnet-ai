"""One object, one Detection row, when a survey's frames overlap.

`ghostnet.iter_survey_frames` cuts an .xtf/.sdf into tiles that overlap their
neighbours (25 % by default), so a seam never cuts an object with no frame
seeing all of it. The consequence for this app: an object in an overlap is
scored in two (up to four) frames, and persisting every sighting would put two
pins on the map, two rows in the review queue and two lines in the report for
one object. The CLI path merges after scoring; this is the same rule applied
as a processing job persists, frame by frame.

How a sighting is decided, as it arrives
----------------------------------------
Frames are scored in order, so a duplicate's partner is usually already in the
database. Each sighting is placed in SURVEY pixels (the tile offsets are in the
frame id the tiler minted, so no schema change) and checked against the
survivors so far, with the rule in `ghostnet.merge` -- same class, same detector
class, overlapping or within 24 px, different frames:

  * no match              -> a new row, as before.
  * match, new one worse  -> not persisted; the survivor's row lists it.
  * match, new one better -> the survivor's row is OVERWRITTEN with the better
                             sighting (frame, box, score, position, mask) and
                             lists the one it replaced. Same primary key, so
                             the map pin and any open page follow it.

A row someone has already reviewed is never overwritten: the reviewer's
decision was made on what that row showed, so the better sighting is recorded
against it instead.

Suppression is visible: `evidence_summary.merged_seam_duplicates` on the
survivor names every sighting folded into it (detection id, frame, confidence),
and the detail page renders evidence keys as they come.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.detection import Detection
from app.models.enums import ReviewStatus
from app.models.sonar_frame import SonarFrame
from app.schemas.ai_contract import AIDetection
from app.services import detection_service

logger = logging.getLogger("ghostnet.seam_merge")

#: Evidence key on the surviving row. Free-form JSON on our side of the
#: contract, so a list rather than text appended to the AI's own `notes`.
MERGED_KEY = "merged_seam_duplicates"

#: Tile size the frame offsets are measured in -- the detector's input size.
TILE = 640


class SeamMerger:
    """Per-job state: survivors so far, one spatial index per source file.

    Per FILE, because each file is tiled from its own row 0: two .xtf lines in
    one survey both have a tile at p000000__x00000, and those are different
    places on the seabed.
    """

    def __init__(self) -> None:
        from ghostnet import merge
        from ghostnet.config import SETTINGS

        self._merge = merge
        self._settings = SETTINGS
        self._indexes: dict[uuid.UUID, Any] = {}
        self.merged = 0

    @classmethod
    def create(cls) -> "SeamMerger | None":
        """A merger, or None when frames cannot overlap: the AI package is not
        installed (no .xtf/.sdf could have been tiled), or tiling is seamless
        (tile_overlap 0, the default) or the merge is switched off. The same
        gate as ghostnet.survey, so the app and the CLI agree."""
        try:
            merger = cls()
        except ImportError:
            return None
        settings = merger._settings
        if not settings.seam_merge or settings.tile_overlap <= 0:
            return None
        return merger

    def _sighting(self, frame: SonarFrame, ai_detection: AIDetection):
        offsets = self._merge.frame_offsets(frame.frame_id)
        if offsets is None or ai_detection.bbox is None or len(ai_detection.bbox) != 4:
            return None
        row0, col0 = offsets
        notes = (ai_detection.evidence_summary or {}).get("notes") or ""
        payload = {"class": ai_detection.class_, "evidence_summary": {"notes": notes}}
        return self._merge.Sighting(
            ref=(None, frame.frame_id),       # (row id once persisted, frame label)
            frame_key=frame.id,
            cls=ai_detection.class_,
            det_cls=self._merge.detector_class(payload),
            score=float(ai_detection.calibrated_confidence or 0.0),
            box=self._merge.survey_box(ai_detection.bbox, row0, col0),
            margin=self._merge.border_margin(ai_detection.bbox, TILE, TILE),
        )

    @staticmethod
    def _describe(ref: str, frame_id: str, score: float | None) -> str:
        return "%s (frame %s, conf %.3f)" % (ref, frame_id, score or 0.0)

    @staticmethod
    def _record(row: Detection, entries: list[str]) -> None:
        evidence = dict(row.evidence_summary or {})
        evidence[MERGED_KEY] = list(evidence.get(MERGED_KEY) or []) + entries
        row.evidence_summary = evidence      # reassigned: plain JSON columns do not track mutation

    def persist(
        self,
        db: Session,
        survey_id: uuid.UUID,
        frame: SonarFrame,
        ai_detection: AIDetection,
    ) -> tuple[Detection, str]:
        """Persist one AI detection, merging it with a seam duplicate.

        Returns (row, outcome) with outcome "created", "merged" (absorbed into
        an existing row) or "replaced" (it overwrote an existing row).
        Raises DetectionValidationError exactly as persist_ai_detection does.
        """
        sighting = self._sighting(frame, ai_detection)
        if sighting is None:
            return detection_service.persist_ai_detection(db, survey_id, frame, ai_detection), "created"

        detection_service.validate_ai_detection(ai_detection)
        index = self._indexes.get(frame.file_id)
        if index is None:
            index = self._indexes[frame.file_id] = self._merge.SeamIndex(self._settings)

        held = index.find(sighting)
        row = db.get(Detection, held.ref[0]) if held is not None else None
        if row is None:
            if held is not None:
                index.remove(held)            # its row is gone (deleted mid-run); start afresh
            row = detection_service.persist_ai_detection(db, survey_id, frame, ai_detection)
            sighting.ref = (row.id, frame.frame_id)
            index.add(sighting)
            return row, "created"

        self.merged += 1
        if sighting.rank > held.rank and row.review_status == ReviewStatus.PENDING:
            replaced = self._describe(row.detection_ref, held.ref[1], row.calibrated_confidence)
            prior = list((row.evidence_summary or {}).get(MERGED_KEY) or [])
            detection_service.replace_with_ai_detection(db, row, frame, ai_detection)
            sighting.ref = (row.id, frame.frame_id)
            sighting.absorbed = held.absorbed + [held]
            index.remove(held)
            index.add(sighting)
            self._record(row, prior + [replaced])
            db.flush()
            return row, "replaced"

        held.absorbed.append(sighting)
        self._record(row, [self._describe(ai_detection.detection_id, frame.frame_id,
                                          ai_detection.calibrated_confidence)])
        db.flush()
        return row, "merged"
