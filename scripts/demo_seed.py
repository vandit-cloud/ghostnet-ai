"""Rebuild the demo state from scratch: upload, process, export both reports.

Run it from the backend's virtualenv, because it talks to a backend that must
already be running (see docs/DEMO_RUNBOOK.md sections 1-2):

    cd app/backend
    .venv/Scripts/python.exe ../../scripts/demo_seed.py

It uses only the stdlib on purpose -- no requests, no httpx -- so it works in
either virtualenv and needs nothing installed.

It does NOT wipe anything. If a survey of the same name already exists you get a
second one, which is usually what you want when rehearsing. To start clean:

    psql ... -c "delete from surveys;"
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE = os.environ.get("GHOSTNET_API", "http://localhost:8000/api/v1")
USERNAME = os.environ.get("GHOSTNET_USER", "operator")
PASSWORD = os.environ.get("GHOSTNET_PASSWORD", "operator123")

REPO = pathlib.Path(__file__).resolve().parent.parent
DEMO = REPO / "demo"
XTF = DEMO / "NBP0505_line01B_demo.xtf"
REPORTS = DEMO / "reports"

SURVEY_NAME = "NBP0505 Line 01B — Golfo de Penas"
SURVEY_LOCATION = "Golfo de Penas, Chile"
SURVEY_DESCRIPTION = "Side-scan sonar, NBP0505 cruise (2005). 40 MB slice of line 01B."


def api(path, data=None, token=None, method="GET", raw=False):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    # ensure_ascii=False plus an explicit utf-8 encode: survey names carry
    # non-ASCII (an em dash here) and must round-trip intact.
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    try:
        with urllib.request.urlopen(req, body) as response:
            payload = response.read()
            return payload if raw else json.loads(payload or b"{}")
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")
        raise SystemExit(f"{method} {path} failed with HTTP {err.code}:\n  {detail}") from None
    except urllib.error.URLError as err:
        raise SystemExit(
            f"Cannot reach {BASE}. Is the backend running? (runbook section 2)\n  {err.reason}"
        ) from None


def upload(path, token, filepath: pathlib.Path):
    """Multipart upload, hand-rolled to keep this stdlib-only."""
    boundary = "----" + uuid.uuid4().hex
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filepath.name}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode()
    tail = f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        BASE + path, data=head + filepath.read_bytes() + tail, method="POST"
    )
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as err:
        raise SystemExit(f"Upload failed with HTTP {err.code}:\n  {err.read().decode()}") from None


def main() -> int:
    if not XTF.exists():
        raise SystemExit(
            f"Missing {XTF}.\nRegenerate it with the head -c command in "
            f"docs/DEMO_RUNBOOK.md section 0."
        )

    token = api("/auth/login", {"username": USERNAME, "password": PASSWORD}, method="POST")[
        "access_token"
    ]
    print("logged in as", USERNAME)

    survey = api(
        "/surveys",
        {"name": SURVEY_NAME, "location": SURVEY_LOCATION, "description": SURVEY_DESCRIPTION},
        token=token,
        method="POST",
    )
    survey_id = survey["id"]
    print("survey :", survey_id)
    # Stamp the id where the runbook's curl and psql examples can find it. Left
    # unwritten it goes stale the first time the demo is re-seeded, and the map
    # endpoint queried with a dead id used to answer 200-with-nothing.
    (DEMO / ".survey_id").write_text(survey_id, encoding="utf-8")
    if survey["name"] != SURVEY_NAME:
        print("  WARNING: the name did not round-trip; check request encoding")

    result = upload(f"/surveys/{survey_id}/files", token, XTF)
    print("upload :", result["validation_status"], "|", result.get("validation_message") or "no warnings")

    job = api(f"/surveys/{survey_id}/process", {}, token=token, method="POST")
    state = job
    for _ in range(300):
        state = api(f"/jobs/{job['id']}", token=token)
        if state["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)
    else:
        raise SystemExit("Processing did not finish within 300 s.")

    print(
        "job    :",
        state["status"],
        f"{state['frames_processed']}/{state['frames_total']} frames,",
        state["detections_found"],
        "detections",
    )
    if state["status"] != "COMPLETED":
        raise SystemExit("Processing did not complete: " + str(state.get("error_summary")))

    survey_map = api(f"/maps/surveys/{survey_id}/detections", token=token)
    print("map    :", len(survey_map["markers"]), "markers,", len(survey_map["track"]), "track points")

    REPORTS.mkdir(parents=True, exist_ok=True)
    for fmt in ("csv", "json"):
        # `type` is required alongside `format`; omitting it is a 422.
        report = api(
            "/reports",
            {"survey_id": survey_id, "type": "full_survey", "format": fmt},
            token=token,
            method="POST",
        )
        time.sleep(2)  # generation is asynchronous
        data = api(f"/reports/{report['id']}/download", token=token, raw=True)
        out = REPORTS / f"NBP0505_line01B_full_survey.{fmt}"
        out.write_bytes(data)
        print(f"report : {out.relative_to(REPO)}  {len(data):,} bytes")

    print("\nDemo state ready. Open http://localhost:3000")
    return 0


if __name__ == "__main__":
    sys.exit(main())
