"""Run the trained model on your own images and see what it says.

    python ai/scripts/try_model.py --images path/to/pic.png
    python ai/scripts/try_model.py --images path/to/folder --out ai/experiments/tryout
    python ai/scripts/try_model.py --images folder --conf 0.10

This is the ONLY way to test the model that tests what we actually ship. It
calls ghostnet.detect(), the same function Member 2 imports, so what you see
here is the contract payload -- calibrated confidence, the review policy, the
warnings -- not raw YOLO output. Testing the .pt file directly with ultralytics
would exercise a code path nobody uses.

Writes an annotated copy of each image plus the exact JSON payload, so a
surprising result can be traced instead of argued about.

Confidence shown is CALIBRATED, never the raw score
---------------------------------------------------
A raw detector score is a ranking number, not a probability. The calibrated one
went through the fitted temperature and is the number a human should ever see.
Both are written to the JSON; only the calibrated one is drawn.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import cv2

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}

# Distinct on sonar greyscale, and distinguishable to the ~8% of men with
# red-green colour blindness: amber for a detection, blue for a low-confidence
# one held below the review floor.
COLOUR_REPORTED = (0, 170, 255)      # BGR amber
COLOUR_BELOW_FLOOR = (255, 160, 0)   # BGR blue


def show(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT.parent))
    except ValueError:
        return str(path)


def collect(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(p for p in target.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES)


def annotate(img, detections, floor: float):
    for d in detections:
        x, y, w, h = (int(v) for v in d["bbox"])
        conf = d["calibrated_confidence"]
        reported = conf >= floor
        colour = COLOUR_REPORTED if reported else COLOUR_BELOW_FLOOR
        cv2.rectangle(img, (x, y), (x + w, y + h), colour, 2)
        label = f'{d["class"]} {conf:.2f}'
        if not reported:
            label += " (below floor)"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        ty = max(th + 4, y)
        cv2.rectangle(img, (x, ty - th - 4), (x + tw + 4, ty), colour, -1)
        cv2.putText(img, label, (x + 2, ty - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    return img


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the trained detector on your own images.")
    ap.add_argument("--images", required=True, help="an image file or a folder of them")
    ap.add_argument("--weights", default=None,
                    help="default: $GHOSTNET_WEIGHTS, else the newest run's best.pt")
    ap.add_argument("--out", default=None, help="output dir (default ai/experiments/tryout)")
    ap.add_argument("--conf", type=float, default=None,
                    help="review floor to DRAW at. Boxes below it are still shown, dimmed. "
                         "Defaults to the configured review_floor_artificial.")
    ap.add_argument("--json-only", action="store_true", help="skip the annotated images")
    args = ap.parse_args()

    target = Path(args.images).expanduser()
    if not target.exists():
        print(f"nothing at {target}")
        return 1

    images = collect(target)
    if not images:
        print(f"no images under {target} (looked for {', '.join(sorted(IMAGE_SUFFIXES))})")
        return 1

    if args.weights:
        os.environ["GHOSTNET_WEIGHTS"] = str(Path(args.weights).expanduser().resolve())
    elif not os.environ.get("GHOSTNET_WEIGHTS"):
        runs = sorted((AI_ROOT / "experiments").glob("*/weights/best.pt"),
                      key=lambda p: p.stat().st_mtime, reverse=True)
        if runs:
            os.environ["GHOSTNET_WEIGHTS"] = str(runs[0])
            print(f"  no --weights given; using the newest run: {show(runs[0])}")

    from ghostnet import SETTINGS, detect, warmup  # noqa: E402  (after the env var is set)

    floor = args.conf if args.conf is not None else SETTINGS.review_floor_artificial
    out_dir = Path(args.out).expanduser() if args.out else AI_ROOT / "experiments" / "tryout"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  weights  {os.environ.get('GHOSTNET_WEIGHTS', '(none -- detections will be empty)')}")
    print(f"  images   {len(images)} from {show(target)}")
    print(f"  floor    {floor} on CALIBRATED confidence")
    print(f"  output   {show(out_dir)}\n")

    if not warmup():
        print("  ! no model loaded. detect() will return empty payloads with a warning set.")
        print("    That is the documented behaviour, not a crash -- but you wanted a test, so:")
        print("    pass --weights, or set GHOSTNET_WEIGHTS.\n")

    summary = []
    for path in images:
        payload = detect(str(path), {"survey_id": "TRYOUT", "frame_id": path.stem})
        dets = payload.get("detections") or []
        reported = [d for d in dets if d["calibrated_confidence"] >= floor]

        (out_dir / f"{path.stem}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

        if not args.json_only:
            img = cv2.imread(str(path))
            if img is not None:
                cv2.imwrite(str(out_dir / f"{path.stem}_annotated.jpg"), annotate(img, dets, floor))

        top = max((d["calibrated_confidence"] for d in dets), default=0.0)
        summary.append((path.name, len(reported), len(dets) - len(reported), top,
                        payload.get("warnings") or []))
        print(f"  {path.name:<44} reported={len(reported)}  below_floor={len(dets) - len(reported)}  top={top:.3f}")

    n_with = sum(1 for _, r, _, _, _ in summary if r)
    print(f"\n  {n_with} of {len(summary)} images had at least one detection at or above {floor}")

    warned = {w for _, _, _, _, ws in summary for w in ws}
    if warned:
        print("\n  warnings raised (these explain anything odd above):")
        for w in sorted(warned):
            print(f"    - {w}")

    print(f"\n  annotated images and payloads: {show(out_dir)}")
    print("  Amber = reported to a reviewer. Blue = found but held below the floor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
