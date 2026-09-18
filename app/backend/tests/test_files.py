import io
import json


def _create_survey(client, auth_headers):
    return client.post("/api/v1/surveys", json={"name": "Upload Survey"}, headers=auth_headers).json()


def test_upload_valid_image_with_metadata(client, auth_headers):
    survey = _create_survey(client, auth_headers)
    metadata = json.dumps({"latitude": 20.1, "longitude": 70.1, "depth": 15.5, "timestamp": "2026-08-30T10:00:00"})

    response = client.post(
        f"/api/v1/surveys/{survey['id']}/files",
        files={"file": ("frame1.png", io.BytesIO(b"\x89PNG\r\n\x1a\nfakepngbytes"), "image/png")},
        data={"metadata": metadata},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["validation_status"] == "VALID"
    assert body["metadata_status"] == "VALID"

    listing = client.get(f"/api/v1/surveys/{survey['id']}/files", headers=auth_headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1


def test_upload_rejects_unsupported_format(client, auth_headers):
    survey = _create_survey(client, auth_headers)
    response = client.post(
        f"/api/v1/surveys/{survey['id']}/files",
        files={"file": ("payload.exe", io.BytesIO(b"MZfake"), "application/octet-stream")},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["validation_status"] == "INVALID"


def test_upload_rejects_bad_metadata_coordinates(client, auth_headers):
    survey = _create_survey(client, auth_headers)
    metadata = json.dumps({"latitude": 999, "longitude": 70.1})
    response = client.post(
        f"/api/v1/surveys/{survey['id']}/files",
        files={"file": ("frame2.png", io.BytesIO(b"\x89PNG\r\n\x1a\nfakepngbytes"), "image/png")},
        data={"metadata": metadata},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["metadata_status"] == "INVALID"


def test_an_uploaded_image_frame_points_at_a_file_that_exists(client, auth_headers, db_session):
    """An uploaded PNG must produce a frame the detector can actually open.

    `image_reference` is handed straight to the AI adapter as a filesystem
    path. This branch used to store the storage-relative KEY
    ("<survey_id>/<unique_name>"), which resolves against the server's working
    directory instead of the storage root -- so cv2.imread returned None,
    detect() recorded "image not found" as a warning rather than an error, and
    the job completed successfully having found nothing.

    The failure mode is the reason this test asserts on the filesystem rather
    than on a status code: every response along the way was a 2xx, the file was
    marked VALID, the frame row existed, and the job reported COMPLETED. The
    only visible symptom was a survey of uploaded images that never produced a
    single detection, which reads as a weak model rather than a broken path.

    Same defect the XTF branch was fixed for in 144986c; this branch was
    missed.
    """
    import os

    from app.models.sonar_frame import SonarFrame

    survey = _create_survey(client, auth_headers)
    response = client.post(
        f"/api/v1/surveys/{survey['id']}/files",
        files={"file": ("legible.png", io.BytesIO(b"\x89PNG\r\n\x1a\nfakepngbytes"), "image/png")},
        data={"metadata": json.dumps({"latitude": 9.06, "longitude": 79.21})},
        headers=auth_headers,
    )
    assert response.status_code == 201

    frame = (
        db_session.query(SonarFrame)
        .filter(SonarFrame.survey_id == survey["id"])
        .one()
    )
    assert os.path.isabs(frame.image_reference), (
        f"image_reference must be resolvable by the AI adapter, got {frame.image_reference!r}"
    )
    assert os.path.exists(frame.image_reference), (
        f"{frame.image_reference!r} does not exist; the detector would silently find nothing"
    )

    # And it must still be servable through the storage backend, which is the
    # other consumer of this column.
    image = client.get(f"/api/v1/frames/{frame.id}/image", headers=auth_headers)
    assert image.status_code == 200
    assert image.content.startswith(b"\x89PNG")


# ---------------------------------------------------------------------------
# Per-file delete.
#
# This path had no coverage at all, which mattered more than the usual gap: it
# is the only destructive operation scoped narrower than a whole survey, it
# cascades to frames and detections, and it is guarded by both a survey-scoped
# lookup and a 409 while a job is running. Each of those is a place where an
# ordinary refactor could silently widen the blast radius.
# ---------------------------------------------------------------------------


def _upload_png(client, auth_headers, survey_id, name="frame.png"):
    return client.post(
        f"/api/v1/surveys/{survey_id}/files",
        files={"file": (name, io.BytesIO(b"\x89PNG\r\n\x1a\nfakepngbytes"), "image/png")},
        data={"metadata": json.dumps({"latitude": 9.06, "longitude": 79.21})},
        headers=auth_headers,
    ).json()


def test_delete_file_removes_the_row_and_its_frames(client, auth_headers, db_session):
    from app.models.sonar_frame import SonarFrame

    survey = _create_survey(client, auth_headers)
    uploaded = _upload_png(client, auth_headers, survey["id"])

    assert db_session.query(SonarFrame).filter(SonarFrame.survey_id == survey["id"]).count() == 1

    response = client.delete(
        f"/api/v1/surveys/{survey['id']}/files/{uploaded['id']}", headers=auth_headers
    )
    assert response.status_code == 204

    assert client.get(f"/api/v1/surveys/{survey['id']}/files", headers=auth_headers).json() == []
    # The frame cascades with its file. Asserted through a fresh query because
    # passive_deletes leaves the DB, not the session, to do the cascade.
    db_session.expire_all()
    assert db_session.query(SonarFrame).filter(SonarFrame.survey_id == survey["id"]).count() == 0


def test_delete_file_only_works_through_its_own_survey(client, auth_headers):
    """A file id alone must not be enough.

    Otherwise pasting the wrong survey into the URL deletes a file out of a
    survey the caller was not even looking at, and the 404 has to be
    indistinguishable from "no such file" so the endpoint does not confirm the
    existence of things outside the requested survey.
    """
    survey_a = _create_survey(client, auth_headers)
    survey_b = _create_survey(client, auth_headers)
    uploaded = _upload_png(client, auth_headers, survey_a["id"])

    response = client.delete(
        f"/api/v1/surveys/{survey_b['id']}/files/{uploaded['id']}", headers=auth_headers
    )
    assert response.status_code == 404

    # ...and the file is still there.
    assert len(client.get(f"/api/v1/surveys/{survey_a['id']}/files", headers=auth_headers).json()) == 1


def test_delete_file_is_refused_while_a_job_is_running(client, auth_headers, db_session):
    """409 rather than a cascade that pulls rows out from under a live job."""
    from app.models.enums import JobStatus
    from app.models.processing_job import ProcessingJob

    survey = _create_survey(client, auth_headers)
    uploaded = _upload_png(client, auth_headers, survey["id"])

    db_session.add(ProcessingJob(survey_id=survey["id"], frames_total=1, status=JobStatus.PROCESSING))
    db_session.commit()

    response = client.delete(
        f"/api/v1/surveys/{survey['id']}/files/{uploaded['id']}", headers=auth_headers
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SURVEY_PROCESSING"


def test_delete_unknown_file_is_404(client, auth_headers):
    import uuid as _uuid

    survey = _create_survey(client, auth_headers)
    response = client.delete(
        f"/api/v1/surveys/{survey['id']}/files/{_uuid.uuid4()}", headers=auth_headers
    )
    assert response.status_code == 404
