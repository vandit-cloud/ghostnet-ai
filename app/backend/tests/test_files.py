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
