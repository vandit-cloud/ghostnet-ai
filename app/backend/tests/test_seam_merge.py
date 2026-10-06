"""One object seen from two overlapping frames must be ONE Detection row.

Frames cut from an .xtf/.sdf overlap their neighbours (ghostnet tile_overlap,
25 % by default). Persisting every sighting would put two pins on the map and
two entries in the review queue for one object; these pin the per-job merge
that prevents it, and that it never hides anything silently.
"""

import asyncio
import uuid

from app.models.detection import Detection
from app.models.enums import ReviewStatus
from app.models.processing_job import ProcessingJob
from app.models.sonar_frame import SonarFrame
from app.models.survey import Survey
from app.models.survey_file import SurveyFile
from app.schemas.ai_contract import AIDetection, AIInferResponse
from app.services import processing_service
from app.services.seam_merge_service import MERGED_KEY, SeamMerger

# Two tiles of one line, 480 px apart across-track: survey col = offset + x.
LEFT, RIGHT = "line01__p000000__x00000", "line01__p000000__x00480"


def _survey(db, *frame_ids, files=1):
    survey = Survey(name="seam-" + uuid.uuid4().hex[:6])
    db.add(survey)
    db.flush()
    out_files = []
    for i in range(files):
        f = SurveyFile(
            survey_id=survey.id, filename=f"line{i}.xtf", storage_reference=f"{survey.id}/line{i}.xtf",
            format="xtf", size=1, checksum="x", validation_status="VALID", metadata_status="VALID",
        )
        db.add(f)
        out_files.append(f)
    db.flush()
    frames = []
    for i, fid in enumerate(frame_ids):
        fr = SonarFrame(
            survey_id=survey.id, file_id=out_files[i % files].id if files > 1 else out_files[0].id,
            frame_id=fid, image_reference=f"/tmp/{fid}.png", ping_id="0",
        )
        db.add(fr)
        frames.append(fr)
    db.flush()
    return survey, frames


def _ai(ref, conf, bbox, cls="debris", notes="detector class: wreck"):
    return AIDetection(
        detection_id=ref, class_=cls, raw_score=conf, calibrated_confidence=conf, uncertainty="medium",
        bbox=list(bbox), model_version="test", evidence_summary={"notes": notes},
    )


def _rows(db, survey):
    return db.query(Detection).filter(Detection.survey_id == survey.id).all()


def test_a_worse_second_sighting_is_folded_into_the_first_row(db_session):
    survey, (left, right) = _survey(db_session, LEFT, RIGHT)
    m = SeamMerger()
    row, outcome = m.persist(db_session, survey.id, left, _ai("D-LEFT0001", 0.55, (560, 200, 40, 40)))
    assert outcome == "created"
    row2, outcome = m.persist(db_session, survey.id, right, _ai("D-RGHT0001", 0.41, (82, 201, 40, 40)))
    assert outcome == "merged" and row2.id == row.id
    rows = _rows(db_session, survey)
    assert len(rows) == 1
    assert rows[0].detection_ref == "D-LEFT0001"
    assert "D-RGHT0001" in rows[0].evidence_summary[MERGED_KEY][0]       # named, not silent


def test_a_better_second_sighting_takes_over_the_same_row(db_session):
    """Same primary key, so a map pin or an open detail page follows it."""
    survey, (left, right) = _survey(db_session, LEFT, RIGHT)
    m = SeamMerger()
    row, _ = m.persist(db_session, survey.id, left, _ai("D-LEFT0002", 0.35, (600, 200, 40, 40)))
    first_id = row.id
    row2, outcome = m.persist(db_session, survey.id, right, _ai("D-RGHT0002", 0.62, (120, 200, 40, 40)))
    assert outcome == "replaced" and row2.id == first_id
    rows = _rows(db_session, survey)
    assert len(rows) == 1
    assert rows[0].detection_ref == "D-RGHT0002"
    assert rows[0].frame_id == right.id and rows[0].bbox_x == 120
    assert rows[0].calibrated_confidence == 0.62
    assert any("D-LEFT0002" in e for e in rows[0].evidence_summary[MERGED_KEY])
    assert rows[0].evidence_summary["notes"] == "detector class: wreck"   # the AI's own evidence kept


def test_a_reviewed_row_is_never_overwritten(db_session):
    survey, (left, right) = _survey(db_session, LEFT, RIGHT)
    m = SeamMerger()
    row, _ = m.persist(db_session, survey.id, left, _ai("D-LEFT0003", 0.35, (600, 200, 40, 40)))
    row.review_status = ReviewStatus.ACCEPTED_ARTIFICIAL
    db_session.flush()
    row2, outcome = m.persist(db_session, survey.id, right, _ai("D-RGHT0003", 0.62, (120, 200, 40, 40)))
    assert outcome == "merged"
    assert row2.detection_ref == "D-LEFT0003"
    assert any("D-RGHT0003" in e for e in row2.evidence_summary[MERGED_KEY])


def test_different_classes_or_places_stay_separate(db_session):
    survey, (left, right) = _survey(db_session, LEFT, RIGHT)
    m = SeamMerger()
    m.persist(db_session, survey.id, left, _ai("D-A", 0.5, (560, 200, 40, 40)))
    _, o1 = m.persist(db_session, survey.id, right, _ai("D-B", 0.5, (80, 200, 40, 40), cls="ghost_net", notes=""))
    _, o2 = m.persist(db_session, survey.id, right, _ai("D-C", 0.5, (80, 200, 40, 40), notes="detector class: plane"))
    _, o3 = m.persist(db_session, survey.id, right, _ai("D-D", 0.5, (80, 400, 40, 40)))
    assert (o1, o2, o3) == ("created", "created", "created")
    assert len(_rows(db_session, survey)) == 4


def test_two_files_in_one_survey_are_different_seabed(db_session):
    """Both lines have a tile at p000000__x00000; that is not one place."""
    survey, (a, b) = _survey(db_session, LEFT, LEFT, files=2)
    m = SeamMerger()
    m.persist(db_session, survey.id, a, _ai("D-F1", 0.5, (100, 100, 40, 40)))
    _, outcome = m.persist(db_session, survey.id, b, _ai("D-F2", 0.5, (100, 100, 40, 40)))
    assert outcome == "created"


def test_uploaded_images_are_never_merged(db_session):
    """Frames the tiler did not cut cannot overlap; nothing to merge."""
    survey, (a, b) = _survey(db_session, "upload-1", "upload-2")
    m = SeamMerger()
    m.persist(db_session, survey.id, a, _ai("D-U1", 0.5, (100, 100, 40, 40)))
    _, outcome = m.persist(db_session, survey.id, b, _ai("D-U2", 0.5, (100, 100, 40, 40)))
    assert outcome == "created"


class _FakeAdapter:
    """Sees one object at survey column 600-640, row 200-240, from any tile holding it."""

    def analyze_frame(self, survey_id, frame_id, image_path, metadata):
        x0 = int(frame_id.rsplit("__x", 1)[1])
        dets = []
        if x0 <= 600 and 640 <= x0 + 640:
            dets.append(_ai("D-%05d" % x0, round(0.4 + x0 / 10000, 3), (600 - x0, 200, 40, 40)))
        return AIInferResponse(survey_id=survey_id, frame_id=frame_id, detections=dets)


def test_a_processing_run_persists_one_row_per_object(db_session, monkeypatch):
    from dataclasses import replace

    import ghostnet.config as cfg

    # Overlap is opt-in (off by default); this run is what turning it on buys.
    monkeypatch.setattr(cfg, "SETTINGS", replace(cfg.SETTINGS, tile_overlap=0.25))
    survey, frames = _survey(db_session, LEFT, RIGHT, "line01__p000000__x00960")
    job = ProcessingJob(survey_id=survey.id, frames_total=len(frames))
    db_session.add(job)
    db_session.commit()

    events = []

    async def _emit(survey_id, event, payload):
        events.append(event)

    async def _no_sleep(*a, **k):
        return None

    monkeypatch.setattr(processing_service, "get_ai_adapter", lambda: _FakeAdapter())
    monkeypatch.setattr(processing_service, "_emit", _emit)
    monkeypatch.setattr(processing_service.asyncio, "sleep", _no_sleep)
    asyncio.run(processing_service._run_job(job.id))

    db_session.expire_all()
    rows = _rows(db_session, survey)
    assert len(rows) == 1                                   # one pin, one review entry
    assert rows[0].detection_ref == "D-00480"               # the better sighting won
    assert len(rows[0].evidence_summary[MERGED_KEY]) == 1
    assert db_session.get(ProcessingJob, job.id).detections_found == 1
    assert events.count("detection.created") == 1 and events.count("detection.updated") == 1


def test_no_merger_when_tiles_do_not_overlap(monkeypatch):
    """Seamless tiling (the default) has no seam duplicates to merge, and two
    boxes in adjacent tiles must not be folded together -- same gate as the CLI."""
    from dataclasses import replace

    import ghostnet.config as cfg

    monkeypatch.setattr(cfg, "SETTINGS", replace(cfg.SETTINGS, tile_overlap=0.0))
    assert SeamMerger.create() is None
    monkeypatch.setattr(cfg, "SETTINGS", replace(cfg.SETTINGS, tile_overlap=0.25, seam_merge=False))
    assert SeamMerger.create() is None
    monkeypatch.setattr(cfg, "SETTINGS", replace(cfg.SETTINGS, tile_overlap=0.25, seam_merge=True))
    assert SeamMerger.create() is not None
