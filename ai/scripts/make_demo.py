"""Build the data for the demo page: real model output on real test tiles.

    python ai/scripts/make_demo.py --weights ai/experiments/<run>/weights/best.pt

Writes ai/experiments/<run>/demo_data.json -- images as data URIs plus the exact
contract payload the pipeline produced for each.

The selection is deliberately mixed
-----------------------------------
It would be easy to pick twelve confident hits and call it a demo. This picks
hits, MISSES, correct rejections of empty seabed, and FALSE POSITIVES, in
roughly the proportion the test metrics imply.

That is not modesty. A teammate who has seen the failure modes can build a
review UI that handles them; one who has only seen the wins will design for a
model that does not exist, and find out during integration. The false positives
are also the clearest possible statement of what the review workflow is FOR.

Every payload here is the untouched output of ghostnet.detect. Nothing is
edited for presentation.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

import cv2

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

from ghostnet import SETTINGS, detect  # noqa: E402
from ghostnet.contract import validate  # noqa: E402

PROCESSED = AI_ROOT / "data" / "processed"


def show(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT.parent))
    except ValueError:
        return str(path)


def data_uri(path: Path, max_side: int = 512, quality: int = 82) -> str:
    img = cv2.imread(str(path))
    h, w = img.shape[:2]
    if max(h, w) > max_side:
        s = max_side / max(h, w)
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode("ascii")


def truth_boxes(label: Path) -> list[list[float]]:
    out = []
    if not label.exists():
        return out
    for line in label.read_text(encoding="utf-8").split("\n"):
        if line.strip():
            c, cx, cy, bw, bh = line.split()[:5]
            out.append([int(c), float(cx), float(cy), float(bw), float(bh)])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate demo data from real model output.")
    ap.add_argument("--weights", required=True)
    ap.add_argument("--split", default="test")
    ap.add_argument("--hits", type=int, default=5)
    ap.add_argument("--misses", type=int, default=3)
    ap.add_argument("--clean", type=int, default=3)
    ap.add_argument("--false-alarms", type=int, default=3)
    ap.add_argument("--conf", type=float, default=0.20, help="the review floor the policy uses")
    args = ap.parse_args()

    weights = Path(args.weights)
    if not weights.exists():
        print(f"weights not found: {weights}")
        return 1

    SETTINGS.weights_path = weights
    SETTINGS.model_version = weights.parent.parent.name

    root = PROCESSED / args.split
    images_dir, labels_dir = root / "images", root / "labels"
    if not images_dir.is_dir():
        print(f"no {args.split} split at {root}")
        return 1

    buckets: dict[str, list] = {"hit": [], "miss": [], "clean": [], "false_alarm": []}
    want = {"hit": args.hits, "miss": args.misses, "clean": args.clean, "false_alarm": args.false_alarms}

    files = sorted(images_dir.iterdir())
    print(f"\n  scanning {len(files)} {args.split} tiles for a representative mix\n")

    for i, img in enumerate(files):
        if all(len(buckets[k]) >= want[k] for k in want):
            break
        label = labels_dir / (img.stem + ".txt")
        gt = truth_boxes(label)
        payload = detect(img, {"survey_id": "DEMO", "frame_id": img.stem})
        reported = [d for d in payload["detections"] if d["calibrated_confidence"] >= args.conf]

        if gt and reported:
            kind = "hit"
        elif gt and not reported:
            kind = "miss"
        elif not gt and reported:
            kind = "false_alarm"
        else:
            kind = "clean"

        if len(buckets[kind]) >= want[kind]:
            continue
        frame = cv2.imread(str(img))
        buckets[kind].append({
            "kind": kind,
            "frame_id": img.stem,
            # The contract carries bbox in PIXELS but not the frame size, so
            # any renderer needs the dimensions to scale boxes onto a
            # displayed image. Member 2 has the image file and can read them;
            # recorded here so the demo page does not have to.
            "width": int(frame.shape[1]),
            "height": int(frame.shape[0]),
            "source": img.stem.split("__")[0],
            "image": data_uri(img),
            "truth": gt,
            "payload": payload,
            "reported": reported,
            "contract_problems": validate(payload),
        })
        if i % 200 == 0:
            print(f"    {i}/{len(files)}  " + "  ".join(f"{k}:{len(v)}" for k, v in buckets.items()), end="\r")

    cases = buckets["hit"] + buckets["miss"] + buckets["clean"] + buckets["false_alarm"]
    if not cases:
        print("no cases found -- check the weights and split.")
        return 1

    run_dir = weights.parent.parent
    metrics_path, background_path = run_dir / "test_metrics.json", run_dir / "background_metrics.json"
    out = {
        "model_version": SETTINGS.model_version,
        "weights": str(weights),
        "split": args.split,
        "review_floor": args.conf,
        "provenance": SETTINGS.provenance(),
        "classes": ["wreck", "plane", "debris"],
        "test_metrics": json.loads(metrics_path.read_text()) if metrics_path.exists() else None,
        "background_metrics": json.loads(background_path.read_text()) if background_path.exists() else None,
        "counts": {k: len(v) for k, v in buckets.items()},
        "cases": cases,
    }
    dest = run_dir / "demo_data.json"
    dest.write_text(json.dumps(out), encoding="utf-8")
    size_mb = dest.stat().st_size / 1e6
    print("\n\n  " + "  ".join(f"{k}={len(v)}" for k, v in buckets.items()))
    print(f"  wrote {show(dest)}  ({size_mb:.1f} MB)")
    bad = [c for c in cases if c["contract_problems"]]
    if bad:
        print(f"  ! {len(bad)} payload(s) failed contract validation")
        return 1
    print("  every payload validates against the contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
