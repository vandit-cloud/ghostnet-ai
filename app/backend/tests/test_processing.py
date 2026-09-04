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
