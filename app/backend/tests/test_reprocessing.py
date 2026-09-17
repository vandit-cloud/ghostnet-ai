"""Tests for re-processing a survey that has already been scored.

`start_processing` was idempotent against a job already RUNNING ("refresh must
not restart processing", spec section 17) and had no opinion at all about a job
already FINISHED. So a second Process on a completed survey re-scored every
frame and APPENDED a second full set of detections.

Found by running the same 40-frame survey three times: 15 detections, three
identical copies at each of five positions, and duplicated map pins, review
queue entries and report rows.

`force_restart` was already declared on ProcessingStartRequest and read by
nothing, which is why this went unnoticed -- a caller could pass it and get the
duplicate behaviour anyway.
"""

import uuid

import pytest

from app.core.errors import ApiError
from app.models.detection import Detection
from app.models.enums import ReviewStatus
from app.models.sonar_frame import SonarFrame
from app.models.survey import Survey
from app.models.survey_file import SurveyFile
from app.services import processing_service


@pytest.fixture()
def no_background_job(monkeypatch):
    """Stop start_processing from scheduling the async scoring task.

    These tests are about what happens SYNCHRONOUSLY before the job is
    scheduled -- the refusal, and the delete that force_restart does first.
    Without this, `asyncio.create_task` raises "no running event loop" in a
    sync test and the coroutine is left un-awaited.
    """
    created = []
    monkeypatch.setattr(
        "app.services.processing_service.asyncio.create_task",
        lambda coro, *a, **kw: (coro.close(), created.append(1))[0],
    )
    return created


@pytest.fixture()
def scored_survey(db_session):
    """A survey with one frame and two detections already on it."""
    survey = Survey(name="reprocess-" + uuid.uuid4().hex[:6])
    db_session.add(survey)
    db_session.flush()
    sf = SurveyFile(
        survey_id=survey.id, filename="line.xtf", storage_reference="x/line.xtf",
        format="xtf", size=1, checksum="c",
    )
    db_session.add(sf)
    db_session.flush()
    frame = SonarFrame(
        survey_id=survey.id, file_id=sf.id, frame_id="f0", image_reference="f0.png",
    )
    db_session.add(frame)
    db_session.flush()
    # detection_ref is globally UNIQUE, and db_session does not roll back
    # between tests, so a hardcoded ref collides with rows an earlier test left
    # behind.
    ref = uuid.uuid4().hex[:6].upper()
    for i in range(2):
        db_session.add(
            Detection(
                detection_ref=f"D-{ref}{i}", survey_id=survey.id, frame_id=frame.id,
                source_file_id=sf.id, detection_class="debris",
                review_status=ReviewStatus.PENDING,
            )
        )
    db_session.commit()
    return survey


def test_a_second_run_is_refused_instead_of_duplicating(db_session, scored_survey):
    """The bug this file exists for. Must NOT quietly append a second set."""
    with pytest.raises(ApiError) as err:
        processing_service.start_processing(db_session, scored_survey.id)

    assert err.value.status_code == 409
    assert err.value.code == "ALREADY_PROCESSED"
    # The message has to tell the caller how to proceed AND what it costs.
    assert "force_restart" in err.value.message
    assert "review" in err.value.message.lower()

    # and nothing was added
    remaining = (
        db_session.query(Detection).filter(Detection.survey_id == scored_survey.id).count()
    )
    assert remaining == 2


def test_force_restart_discards_the_old_detections_first(db_session, scored_survey, no_background_job):
    """With the flag, the previous run is cleared rather than added to -- which
    is the whole reason the default refuses."""
    processing_service.start_processing(db_session, scored_survey.id, force_restart=True)

    # The job runs asynchronously; what matters here is that the OLD rows are
    # gone synchronously, before any new scoring can append to them.
    assert (
        db_session.query(Detection).filter(Detection.survey_id == scored_survey.id).count()
        == 0
    )


def test_a_survey_with_no_detections_needs_no_flag(db_session, no_background_job):
    """The refusal must not block a first run."""
    survey = Survey(name="first-run-" + uuid.uuid4().hex[:6])
    db_session.add(survey)
    db_session.commit()

    job = processing_service.start_processing(db_session, survey.id)
    assert job.survey_id == survey.id
    assert job.frames_total == 0
