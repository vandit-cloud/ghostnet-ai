"""Regression tests for the demo blockers in docs/KNOWN_ISSUES.md.

Each test here corresponds to an entry in that document and fails against the
code as it stood when the walkthrough was written:

* A1 -- a finished job vanished, because the only endpoint that could name it
  stopped naming it the moment it finished.
* A4 -- there was no DELETE route anywhere in the API, so a mistaken upload was
  permanent through the UI.
* B1 -- the dashboard named one survey and counted all of them.
* B2 -- the detections list never said which survey a row came from.
"""

import uuid

from app.models.detection import Detection
from app.models.enums import JobStage, JobStatus, Priority, ReviewStatus
from app.models.processing_job import ProcessingJob
from app.models.sonar_frame import SonarFrame
from app.models.survey import Survey
from app.models.survey_file import SurveyFile
from app.services.dashboard_service import build_dashboard_summary


def _survey_with_detections(db, name_prefix: str, count: int) -> Survey:
    """A survey carrying `count` detections, with the file and frame they hang off."""
    survey = Survey(name=f"{name_prefix}-{uuid.uuid4().hex[:6]}")
    db.add(survey)
    db.flush()

    survey_file = SurveyFile(
        survey_id=survey.id,
        filename="line.xtf",
        storage_reference=f"{survey.id}/line.xtf",
        format="xtf",
        size=1,
        checksum="c",
    )
    db.add(survey_file)
    db.flush()

    frame = SonarFrame(
        survey_id=survey.id, file_id=survey_file.id, frame_id="f0", image_reference="f0.png"
    )
    db.add(frame)
    db.flush()

    # detection_ref is globally UNIQUE and the session is not rolled back
    # between tests, so the refs have to be unique per run.
    ref = uuid.uuid4().hex[:6].upper()
    for i in range(count):
        db.add(
            Detection(
                detection_ref=f"D-{ref}{i}",
                survey_id=survey.id,
                frame_id=frame.id,
                source_file_id=survey_file.id,
                detection_class="debris",
                priority=Priority.HIGH,
                review_status=ReviewStatus.PENDING,
            )
        )
    db.commit()
    return survey


# --------------------------------------------------------------------------
# A1 - a finished job must still be findable
# --------------------------------------------------------------------------


def test_a_finished_job_is_still_reachable_from_its_survey(client, auth_headers, db_session):
    """The A1 regression.

    /jobs/active answers "is something running?" and correctly goes quiet when
    nothing is. The processing page needs "what happened to my run?" answered
    too -- it used to derive the job id from /jobs/active, so on completion the
    id evaporated, the query key changed, and the page reported that no job had
    ever run on a survey that had just produced 40 frames and 5 detections.
    """
    survey = _survey_with_detections(db_session, "finished-job", 1)
    job = ProcessingJob(
        survey_id=survey.id,
        status=JobStatus.COMPLETED,
        stage=JobStage.DONE,
        progress=100,
        frames_total=40,
        frames_processed=40,
        detections_found=5,
    )
    db_session.add(job)
    db_session.commit()

    # The old source of truth is silent, and that is correct behaviour for it.
    active = client.get(f"/api/v1/surveys/{survey.id}/jobs/active", headers=auth_headers)
    assert active.status_code == 200
    assert active.json() is None

    # The new one is not.
    latest = client.get(f"/api/v1/surveys/{survey.id}/jobs/latest", headers=auth_headers)
    assert latest.status_code == 200
    body = latest.json()
    assert body is not None, "a completed job must still be reachable from its survey"
    assert body["id"] == str(job.id)
    assert body["status"] == "COMPLETED"
    # The counts the completion panel reports.
    assert body["frames_processed"] == 40
    assert body["detections_found"] == 5


def test_latest_job_is_null_for_a_survey_that_never_ran(client, auth_headers, db_session):
    """"Never processed" and "processed, then finished" must be distinguishable."""
    survey = Survey(name="never-run-" + uuid.uuid4().hex[:6])
    db_session.add(survey)
    db_session.commit()

    response = client.get(f"/api/v1/surveys/{survey.id}/jobs/latest", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() is None


def test_latest_job_404s_for_an_unknown_survey(client, auth_headers):
    """A bad id is not the same as a survey with no jobs, and must not look like it."""
    response = client.get(f"/api/v1/surveys/{uuid.uuid4()}/jobs/latest", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SURVEY_NOT_FOUND"


def test_latest_job_is_the_most_recent_one(client, auth_headers, db_session):
    """With several runs behind it, the page must show the newest, not the first."""
    survey = _survey_with_detections(db_session, "many-jobs", 1)
    for status in (JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.COMPLETED):
        db_session.add(ProcessingJob(survey_id=survey.id, status=status, stage=JobStage.DONE))
        db_session.commit()  # commit per row so created_at ordering is unambiguous

    body = client.get(
        f"/api/v1/surveys/{survey.id}/jobs/latest", headers=auth_headers
    ).json()
    assert body["status"] == "COMPLETED"


# --------------------------------------------------------------------------
# A4 - delete
# --------------------------------------------------------------------------


def test_a_survey_can_be_deleted_with_everything_derived_from_it(client, auth_headers, db_session):
    """The A4 regression: there was no DELETE route in the whole API.

    The delete has to take the children with it. The cascade is declared at the
    database level, so what this really guards is that the route reaches it --
    a delete that left orphaned detections behind would keep showing them on
    the detections list and the map.
    """
    survey = _survey_with_detections(db_session, "deletable", 3)
    survey_id = survey.id
    db_session.add(ProcessingJob(survey_id=survey_id, status=JobStatus.COMPLETED, stage=JobStage.DONE))
    db_session.commit()

    response = client.delete(f"/api/v1/surveys/{survey_id}", headers=auth_headers)
    assert response.status_code == 204

    db_session.expire_all()
    assert db_session.get(Survey, survey_id) is None
    assert db_session.query(Detection).filter(Detection.survey_id == survey_id).count() == 0
    assert db_session.query(SonarFrame).filter(SonarFrame.survey_id == survey_id).count() == 0
    assert db_session.query(SurveyFile).filter(SurveyFile.survey_id == survey_id).count() == 0
    assert db_session.query(ProcessingJob).filter(ProcessingJob.survey_id == survey_id).count() == 0

    # It is gone from the list, not merely hidden from one query.
    listed = client.get("/api/v1/surveys?page_size=200", headers=auth_headers).json()
    assert str(survey_id) not in [item["id"] for item in listed["items"]]


def test_deleting_a_survey_twice_404s_rather_than_reporting_success(client, auth_headers, db_session):
    """A delete that succeeds on a survey that is not there is a lie about what happened."""
    survey = _survey_with_detections(db_session, "delete-twice", 1)

    assert client.delete(f"/api/v1/surveys/{survey.id}", headers=auth_headers).status_code == 204

    second = client.delete(f"/api/v1/surveys/{survey.id}", headers=auth_headers)
    assert second.status_code == 404
    assert second.json()["error"]["code"] == "SURVEY_NOT_FOUND"


def test_delete_requires_authentication(client, db_session):
    """Destructive and unauthenticated is the wrong pair."""
    survey = _survey_with_detections(db_session, "delete-authz", 1)
    assert client.delete(f"/api/v1/surveys/{survey.id}").status_code == 401
    db_session.expire_all()
    assert db_session.get(Survey, survey.id) is not None


# --------------------------------------------------------------------------
# B1 - the dashboard's numbers belong to the survey it names
# --------------------------------------------------------------------------


def test_dashboard_counts_belong_to_the_survey_it_names(client, auth_headers, db_session):
    """The B1 regression.

    Every stat sits beside `current_survey`'s name, and every stat used to be a
    global count. With four surveys in the database the card credited one
    40-frame survey with 160 frames and 20 detections, which during a demo
    reads as the app inventing detections.
    """
    _survey_with_detections(db_session, "dashboard-other", 7)
    current = _survey_with_detections(db_session, "dashboard-current", 2)
    # current_survey is chosen by updated_at, so make sure this one is newest.
    current.name = current.name + " (current)"
    db_session.commit()

    summary = client.get("/api/v1/dashboard/summary", headers=auth_headers).json()

    assert summary["current_survey"]["id"] == str(current.id)
    assert summary["candidates"] == 2, "counts must be scoped to the named survey"
    assert summary["needs_review"] == 2
    assert summary["high_priority"] == 2
    assert sum(row["count"] for row in summary["class_distribution"]) == 2
    assert sum(row["count"] for row in summary["detection_trend"]) == 2
    assert len(summary["recent_detections"]) == 2
    for detection in summary["recent_detections"]:
        assert detection["id"] in [
            str(d.id)
            for d in db_session.query(Detection).filter(Detection.survey_id == current.id).all()
        ]


def test_dashboard_survives_an_empty_database(db_session):
    """With no survey to scope to, every scoped number is zero rather than an error.

    Driven through the service rather than the HTTP endpoint on purpose: an
    empty database is only reachable by deleting every survey, and committing
    that would pull the rug out from under every test that runs after this one.
    A savepoint keeps the damage inside this function.
    """
    savepoint = db_session.begin_nested()
    try:
        for survey in db_session.query(Survey).all():
            db_session.delete(survey)
        db_session.flush()

        summary = build_dashboard_summary(db_session)
        assert summary.current_survey is None
        assert summary.candidates == 0
        assert summary.frames_processed == 0
        assert summary.needs_review == 0
        assert summary.class_distribution == []
        assert summary.detection_trend == []
        assert summary.recent_detections == []
    finally:
        savepoint.rollback()


# --------------------------------------------------------------------------
# B2 - a detection row says which survey it came from
# --------------------------------------------------------------------------


def test_detections_carry_the_name_of_their_survey(client, auth_headers, db_session):
    """The B2 regression.

    The detections page is reachable from the sidebar with no survey scope, so
    rows from every survey arrive in one undifferentiated list. Without a name
    on the row there is nothing to tell them apart.
    """
    survey = _survey_with_detections(db_session, "named-rows", 2)

    listed = client.get(
        f"/api/v1/detections?survey_id={survey.id}", headers=auth_headers
    ).json()
    assert listed["items"], "expected the detections just created"
    for item in listed["items"]:
        assert item["survey_name"] == survey.name

    detail = client.get(
        f"/api/v1/detections/{listed['items'][0]['id']}", headers=auth_headers
    ).json()
    assert detail["survey_name"] == survey.name
