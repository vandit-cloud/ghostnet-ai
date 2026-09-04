"""Explode an uploaded .xtf sonar file into SonarFrame rows.

Before this, `file_service` created frames only for image extensions
(.png/.jpg/.tif), so uploading the file the sonar actually writes stored a
SurveyFile and produced ZERO frames -- nothing to process, nothing to detect,
no track, an empty map. The upload whitelist accepted .xtf; nothing consumed it.

    frames_created, warnings = ingest_xtf(db, survey_id, file_id, path)

What this deliberately does NOT do
----------------------------------
It does not run detection. `ghostnet.iter_survey_frames` tiles the file and
returns each frame's geometry WITHOUT scoring, so the existing
`processing_service` loop still owns detection -- with its job stages, its
cancellation checks, its websocket progress and its persistence. Scoring here
would mean running the model twice per frame and would route around all of
that.

Why the frame positions matter as much as the detections
--------------------------------------------------------
Each frame gets its own latitude, longitude, heading and timestamp, read from
the sonar's ping headers. That is what `map_service.get_survey_track` reads to
draw the vessel track, and what the time-playback control on the map page
replays. Detection positions alone give a scatter of pins; frame positions give
the line the boat actually travelled -- including across the stretches where
nothing was found, which is most of any real survey.

`depth` and `range` are left NULL on purpose
--------------------------------------------
The Ping carries a depth, and SonarFrame has a column for it, so copying it
across looks free. It is not: `depth` on this model is read by the AI adapter as
context, and the geometry needs ALTITUDE -- height above the seabed, a different
quantity. Populating `depth` invites exactly the substitution that produces a
map which looks right and is wrong by a variable amount. The geometry travels
through `metadata_source="xtf"`, which tells the adapter it can derive its own.
"""

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.sonar_frame import SonarFrame

logger = logging.getLogger("ghostnet.ingest")

#: Sonar container formats this module can explode. `.jsf` is accepted by the
#: upload whitelist but there is no JSF reader, so it is NOT here -- and
#: `ingest_xtf` says so rather than failing silently.
SUPPORTED = {".xtf"}

#: Tiles are written beside the uploaded file, in a folder named after it, so a
#: survey's frames stay together and are servable by the frames image endpoint.
FRAME_SUBDIR = "frames"


def _parse_time(value: str | None) -> datetime:
    """Ping time to an aware datetime, falling back to now.

    The track is ordered by timestamp, so a None here would sort a frame to the
    end and draw a line that doubles back on itself.
    """
    if value:
        try:
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def ingest_xtf(
    db: Session,
    survey_id: uuid.UUID,
    file_id: uuid.UUID,
    storage_path: str | Path,
    max_pings: int | None = None,
) -> tuple[int, list[str]]:
    """Tile an .xtf into SonarFrame rows. Returns (frames_created, warnings).

    `storage_path` is a REAL FILESYSTEM PATH, not a `storage_reference`. Callers
    holding a reference must resolve it first with `storage.path_for()`. The two
    look alike and both end in `.xtf`, so the extension check below passes
    either way and the difference only surfaces as a FileNotFoundError that this
    function turns into a warning -- a file marked VALID with zero frames.

    Adds rows to the session but does NOT commit -- the caller owns the
    transaction, so a bad file cannot leave a survey half-populated.

    Never raises. A missing AI package, an unreadable file or an unsupported
    extension all come back as (0, [reason]), because an upload that cannot be
    tiled is a message to the operator, not a 500.
    """
    warnings: list[str] = []
    path = Path(storage_path)
    ext = path.suffix.lower()

    if ext not in SUPPORTED:
        return 0, [
            f"{ext or 'this file'} cannot be split into frames automatically; "
            "only .xtf is supported. Upload pre-cut images, or convert the file first."
        ]

    try:
        from ghostnet import iter_survey_frames
    except ImportError:
        return 0, [
            "the AI package is not installed on this server, so .xtf files cannot "
            'be split into frames. Install it with: pip install -e "<path>/ai"'
        ]

    out_dir = path.parent / FRAME_SUBDIR / path.stem
    created = 0
    unplaced = 0

    try:
        for frame in iter_survey_frames(path, out_dir=out_dir, max_pings=max_pings):
            position = frame.position
            if position is None or position.latitude is None:
                unplaced += 1
            db.add(
                SonarFrame(
                    survey_id=survey_id,
                    file_id=file_id,
                    frame_id=frame.frame_id,
                    ping_id=str(frame.ping_offset),
                    timestamp=_parse_time(position.timestamp if position else None),
                    image_reference=str(frame.image_path),
                    latitude=position.latitude if position else None,
                    longitude=position.longitude if position else None,
                    heading=position.heading_deg if position else None,
                    # depth and range stay NULL -- see the module docstring.
                    metadata_source="xtf",
                    quality_status="ok" if position else "no_navigation",
                )
            )
            created += 1
    except Exception as exc:
        logger.exception("failed to ingest %s", path.name)
        return 0, [
            f"{path.name} could not be read as an XTF sonar file "
            f"({type(exc).__name__}); no frames were created."
        ]

    if not created:
        return 0, [f"no sonar pings were found in {path.name}; no frames were created."]

    logger.info("ingested %s: %d frames (%d without navigation)", path.name, created, unplaced)
    if unplaced:
        # Said out loud because the visible symptom is a track with gaps in it,
        # and a gap reads as a bug unless someone explains it was missing data.
        warnings.append(
            f"{unplaced} of {created} frames carry no usable navigation; they are "
            "still scored, but will not appear on the survey track."
        )
    return created, warnings
