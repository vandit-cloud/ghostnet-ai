"""Seed the "Showcase" survey: legible frames, live detections, mixed classes.

    cd app/backend
    .venv/Scripts/python.exe ../../scripts/showcase_seed.py

Why this exists
---------------
The NBP0505 survey is a real, unedited 40 MB slice of a 2005 side-scan line,
and it is the honest headline: raw sonar in, detections out. But raw seabed at
1024 samples a channel is mostly speckle, and a reviewer looking at one of its
frames cannot independently tell whether the box is on something. "Trust the
model" is a bad position to argue from.

This survey answers the other question -- *can you see that it is right?* -- by
running the pipeline over frames where the object is unmistakable to the naked
eye: ship hulls with their acoustic shadows, an aircraft with both wings, a
pipeline crossing the swath. A reviewer sees the object, then sees the box on
it, and the two agree without anyone having to be believed.

What is and is not curated
--------------------------
CURATED: which frames are in the survey. They were chosen by
scratchpad tooling that ranked every frame in the held-out test and val splits
by (calibrated confidence x IoU against the human label), then kept the ones
whose object is large enough to read. That selection is a demo decision and
this docstring is where it is admitted.

NOT curated: the detections. Every box in the app is produced by the model at
processing time through the ordinary pipeline, the same code path the raw XTF
takes. No detection is pre-recorded, hand-placed or edited, and no frame was
trained on -- test and val splits only.

SYNTHETIC: the coordinates. The frames come from four countries (Lake Huron,
China, Portugal, a US crab-pot survey), so there is no single real track to
place them on. The positions below exist so the map, the track and the
per-detection localisation have something to draw, and the survey's `source`
field says so in the UI where a judge can read it. Everything else -- the
imagery, the labels, the model output -- is real.

Provenance for every frame, including its original filename and source dataset,
is in demo/showcase/manifest.json.
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

BASE = os.environ.get("GHOSTNET_API", "http://127.0.0.1:8000/api/v1")
USERNAME = os.environ.get("GHOSTNET_USER", "operator")
PASSWORD = os.environ.get("GHOSTNET_PASSWORD", "operator123")

REPO = pathlib.Path(__file__).resolve().parent.parent
SHOWCASE = REPO / "demo" / "showcase"
FRAMES = SHOWCASE / "frames"
XTF_DIR = REPO / "demo" / "xtf"

SURVEY_SOURCE = "Held-out frames, 5 public datasets. Map positions synthetic; see demo/showcase/manifest.json"
SONAR_TYPE = "Side-scan (mixed sources)"

#: One survey per object class, in the order they are seeded. Split rather than
#: combined so a reviewer can open "Submerged Aircraft" and see aircraft,
#: instead of scanning one mixed list for the class they asked about. Each also
#: carries two verified-empty seabed frames, which is the point of the exercise:
#: a detector that boxes everything would look identical on the other five.
SHOWCASE_SURVEYS = [
    ("wrecks",     "Showcase 1 — Sunken Vessels"),
    ("aircraft",   "Showcase 2 — Submerged Aircraft"),
    ("debris",     "Showcase 3 — Seabed Debris & Pipeline"),
    ("ghost_gear", "Showcase 4 — Derelict Fishing Gear"),
]

# Four short synthetic lines in the Gulf of Mannar, off Rameswaram. Chosen
# because it is a real ghost-gear region and it makes the map legible at one
# zoom level; it is NOT where these frames were recorded. Each survey starts on
# its own line so they do not overlap on the map. See the module docstring.
TRACK_STEP = (0.0075, 0.0110)   # ~1.3 km between frames
HEADING_DEG = 55.0
DEPTH_M = 28.0
RANGE_M = 75.0


def api(path, data=None, token=None, method="GET"):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    try:
        with urllib.request.urlopen(req, body) as response:
            payload = response.read()
            return json.loads(payload or b"{}")
    except urllib.error.HTTPError as err:
        raise SystemExit(
            f"{method} {path} failed with HTTP {err.code}:\n  "
            + err.read().decode("utf-8", "replace")
        ) from None
    except urllib.error.URLError as err:
        raise SystemExit(
            f"Cannot reach {BASE}. Is the backend running? (docs/DEMO_RUNBOOK.md section 2)\n"
            f"  {err.reason}"
        ) from None


def upload(survey_id, token, filepath: pathlib.Path, metadata: dict):
    """Multipart upload with per-file metadata, hand-rolled to stay stdlib-only.

    The metadata part is what gives each frame its own position. Uploading the
    batch through the UI dropzone applies ONE metadata set to every file, which
    would stack all fourteen markers on a single point.
    """
    boundary = "----" + uuid.uuid4().hex
    parts = [
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="metadata"\r\n\r\n'
        f"{json.dumps(metadata)}\r\n".encode(),
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filepath.name}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode(),
        filepath.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    req = urllib.request.Request(
        BASE + f"/surveys/{survey_id}/files", data=b"".join(parts), method="POST"
    )
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as err:
        raise SystemExit(
            f"upload of {filepath.name} failed with HTTP {err.code}:\n  "
            + err.read().decode("utf-8", "replace")
        ) from None


def seed_one(token, key: str, name: str) -> tuple[str, dict]:
    """Create one survey from one .xtf and process it.

    One upload, not fourteen: the container carries every frame and its
    navigation, so this is the same gesture a judge makes by dragging the file
    into the browser. The reader splits it into tiles, the pipeline scores
    them, and the track is drawn from the ping headers.
    """
    xtf = XTF_DIR / f"{key}_demo_fixture.xtf"
    if not xtf.exists():
        raise SystemExit(
            f"{xtf} is missing. Build the fixtures first:\n"
            "    .venv/Scripts/python.exe scripts/build_demo_xtf.py"
        )

    survey = api("/surveys", {"name": name, "source": SURVEY_SOURCE,
                              "sonar_type": SONAR_TYPE}, token, "POST")
    survey_id = survey["id"]
    print(f"\n{name}\n  {survey_id}")

    result = upload(survey_id, token, xtf, {})
    print(f"    {xtf.name:34s} {result['validation_status']}")
    if result.get("validation_message"):
        print(f"      note: {result['validation_message']}")

    job = api(f"/surveys/{survey_id}/process", {}, token, "POST")
    for _ in range(600):
        job = api(f"/jobs/{job['id']}", token=token)
        if job["status"] not in ("QUEUED", "VALIDATING", "PROCESSING"):
            break
        time.sleep(0.5)

    detections = api(f"/detections?survey_id={survey_id}&page_size=200", token=token)
    by_class: dict[str, int] = {}
    placed = 0
    for d in detections["items"]:
        by_class[d["detection_class"]] = by_class.get(d["detection_class"], 0) + 1
        if d["latitude"] is not None:
            placed += 1
    print(f"  {job['status']}: {job['frames_processed']}/{job['frames_total']} frames, "
          f"{job['detections_found']} detections  {by_class or '{}'}  "
          f"({placed} with coordinates)")
    return survey_id, by_class


def main() -> None:
    if not XTF_DIR.is_dir() or not any(XTF_DIR.glob("*.xtf")):
        raise SystemExit(
            f"No fixture containers at {XTF_DIR}. Build them with:\n"
            "    .venv/Scripts/python.exe scripts/build_demo_xtf.py\n"
            f"(they are generated from {FRAMES}, which does ship.)"
        )
    if False:
        raise SystemExit(
            f"No showcase frames at {FRAMES}.\n"
            "They ship with the repository; if this is a fresh clone missing them, "
            "rebuild the dataset first (docs/DATA.md) and re-stage."
        )

    token = api("/auth/login", {"username": USERNAME, "password": PASSWORD}, method="POST")["access_token"]

    seeded = []
    for key, name in SHOWCASE_SURVEYS:
        seeded.append((name, *seed_one(token, key, name)))

    print("\n" + "=" * 62)
    for name, survey_id, by_class in seeded:
        print(f"{name}")
        print(f"  http://localhost:3000/app/surveys/{survey_id}")
        print(f"  classes: {by_class or 'none'}")


if __name__ == "__main__":
    main()
