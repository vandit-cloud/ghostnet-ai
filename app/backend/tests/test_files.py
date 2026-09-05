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
