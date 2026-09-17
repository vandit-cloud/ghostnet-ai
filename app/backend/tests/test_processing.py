import io
import json
import time


def test_process_survey_end_to_end(client, auth_headers):
    survey = client.post("/api/v1/surveys", json={"name": "Processing Survey"}, headers=auth_headers).json()

    metadata = json.dumps({"latitude": 20.2, "longitude": 70.2, "depth": 10.0})
    upload = client.post(
        f"/api/v1/surveys/{survey['id']}/files",
        files={"file": ("frame.png", io.BytesIO(b"\x89PNG\r\n\x1a\nfakepngbytes"), "image/png")},
        data={"metadata": metadata},
        headers=auth_headers,
    )
    assert upload.status_code == 201

    start = client.post(f"/api/v1/surveys/{survey['id']}/process", headers=auth_headers)
    assert start.status_code == 202
    job = start.json()
    assert job["frames_total"] == 1

    # Refresh-safety: calling start again while active must return the same job, not a new one.
    restart = client.post(f"/api/v1/surveys/{survey['id']}/process", headers=auth_headers)
    assert restart.json()["id"] == job["id"]

    final_job = None
    for _ in range(50):
        response = client.get(f"/api/v1/jobs/{job['id']}", headers=auth_headers)
        final_job = response.json()
        if final_job["status"] in ("COMPLETED", "PARTIAL", "FAILED"):
            break
        time.sleep(0.2)

    assert final_job is not None
    assert final_job["status"] in ("COMPLETED", "PARTIAL")
    assert final_job["frames_processed"] == 1

    survey_after = client.get(f"/api/v1/surveys/{survey['id']}", headers=auth_headers).json()
    assert survey_after["status"] in ("COMPLETED", "PARTIAL")


def test_get_job_not_found(client, auth_headers):
    response = client.get(
        "/api/v1/jobs/00000000-0000-0000-0000-000000000000", headers=auth_headers
    )
    assert response.status_code == 404


# --- job history (the "vs. last run" comparison) ---------------------------
#
# /jobs/latest answers for the current run only, so a re-processed survey had
# no way to reach the run it replaced even though that row was sitting in the
# table. These cover the endpoint that exposes it.


def _survey_with_jobs(db_session, *detection_counts):
    """A survey carrying one finished job per count, oldest first.

    `created_at` is set explicitly rather than left to `func.now()`: the
    ordering guarantee is the whole point of the endpoint, and two rows
    committed microseconds apart is a weak thing to assert it on.
    """
    import uuid as _uuid
    from datetime import datetime, timedelta, timezone

    from app.models.enums import JobStage, JobStatus
    from app.models.processing_job import ProcessingJob
    from app.models.survey import Survey

    survey = Survey(name="history-" + _uuid.uuid4().hex[:6])
    db_session.add(survey)
    db_session.flush()

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i, found in enumerate(detection_counts):
        db_session.add(
            ProcessingJob(
                survey_id=survey.id,
                status=JobStatus.COMPLETED,
                stage=JobStage.DONE,
                progress=100,
                frames_total=4,
                frames_processed=4,
                detections_found=found,
                created_at=base + timedelta(hours=i),
            )
        )
    db_session.commit()
    return survey


def test_job_history_returns_runs_newest_first(client, auth_headers, db_session):
    survey = _survey_with_jobs(db_session, 2, 5, 9)

    response = client.get(f"/api/v1/surveys/{survey.id}/jobs", headers=auth_headers)
    assert response.status_code == 200

    jobs = response.json()
    assert len(jobs) == 3
    # Index 0 is the current run and index 1 is the one it replaced -- the
    # frontend's comparison reads exactly those two positions.
    assert [j["detections_found"] for j in jobs] == [9, 5, 2]


def test_job_history_respects_limit(client, auth_headers, db_session):
    survey = _survey_with_jobs(db_session, 1, 2, 3, 4)

    response = client.get(f"/api/v1/surveys/{survey.id}/jobs?limit=2", headers=auth_headers)
    assert response.status_code == 200

    jobs = response.json()
    assert [j["detections_found"] for j in jobs] == [4, 3]


def test_job_history_is_empty_for_an_unprocessed_survey(client, auth_headers):
    survey = client.post("/api/v1/surveys", json={"name": "Never Run"}, headers=auth_headers).json()

    response = client.get(f"/api/v1/surveys/{survey['id']}/jobs", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_job_history_404s_for_an_unknown_survey(client, auth_headers):
    """A bad id must stay distinguishable from "never processed", which is why
    this 404s instead of returning the same empty list."""
    response = client.get(
        "/api/v1/surveys/00000000-0000-0000-0000-000000000000/jobs", headers=auth_headers
    )
    assert response.status_code == 404
