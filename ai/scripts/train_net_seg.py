"""Train the single-class ghost_net SEGMENTATION model (D2 / Track D).

    python ai/scripts/train_net_seg.py                    # train
    python ai/scripts/train_net_seg.py --dry-run          # print the plan, train nothing
    python ai/scripts/train_net_seg.py --resume           # continue an interrupted run

Writes ai/experiments/<name>/ ONLY. It never touches ai/models/, so the shipped
gv5 detector and its calibrator cannot be affected by anything here -- the
isolation requirement in EXPERIMENT_GV7_PLAN.md section 1.

Why this is a separate script from train.py
-------------------------------------------
train.py carries chunked-resume and watchdog machinery earned by 14-hour runs on
12,472 images. This dataset is 51 images: an epoch is 13 iterations. Reusing
that machinery would mean maintaining it for a job that finishes between two
cups of tea, and risking the detection training path for a job it was not
written for.

Augmentation, and the one setting that is not a free choice
------------------------------------------------------------
`degrees=0`. Side-scan geometry is not rotation-invariant: the across-track axis
is RANGE, so a rotated tile is not a picture of anything the sonar can produce,
and shadows fall in a direction that rotation makes physically wrong. Flips are
different -- fliplr is the port/starboard mirror and flipud is the vessel
running the other way, both of which are real surveys. So flips stay on and
rotation stays off.

Mosaic is ON despite the tiny dataset, and closed for the last 50 epochs. With
51 images the risk is memorisation, and mosaic is the cheapest defence; closing
it late lets the model finish on undistorted frames.

What this run can and cannot prove
----------------------------------
Its test split is 11 chips. Section 4.3 of the plan is explicit: at this n the
honest output is an upper bound. A number from here is NOT comparable with
gv5's mAP50 -- different task, different label geometry, different metric.
Report it under the Tier 1 rule in section 10.5 (review candidate), never as a
detection claim.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

DATA = AI_ROOT / "data" / "net_seg" / "data.yaml"
PRETRAINED = AI_ROOT / "models" / "pretrained" / "yolo11s-seg.pt"
EXPERIMENTS = AI_ROOT / "experiments"


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=AI_ROOT.parent,
                              capture_output=True, text=True, timeout=10).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser(description="Train the ghost_net segmentation model")
    ap.add_argument("--name", default="gv7d2-netseg")
    ap.add_argument("--weights", default=str(PRETRAINED))
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--epochs", type=int, default=300,
                    help="51 images = 13 iters/epoch, so epochs are cheap; patience ends it early")
    ap.add_argument("--patience", type=int, default=60)
    ap.add_argument("--batch", type=int, default=4, help="4 GB VRAM; 8 does not fit reliably at 640")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default=None, help="default: cuda if available, else cpu")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not Path(args.data).exists():
        print(f"no dataset at {args.data} -- run build_net_seg_dataset.py first")
        return 1
    if not Path(args.weights).exists():
        print(f"no weights at {args.weights} -- run fetch_weights.py first")
        return 1

    from ghostnet.config import resolve_device
    device = args.device if args.device is not None else resolve_device()

    out_dir = EXPERIMENTS / args.name
    print(f"\n  dataset  {args.data}")
    print(f"  weights  {args.weights}")
    print(f"  output   {out_dir}")
    print(f"  device   {device}   batch {args.batch}   imgsz {args.imgsz}   seed {args.seed}")
    print(f"  epochs   {args.epochs} (patience {args.patience})")
    if device == "cpu":
        print("\n  WARNING: device is cpu. On this machine that usually means a broken torch\n"
              "  install rather than a missing GPU -- see the venv note in docs/SETUP.md.")

    if args.dry_run:
        print("\ndry run: nothing trained")
        return 0

    from ultralytics import YOLO

    model = YOLO(args.weights)
    model.train(
        data=args.data,
        task="segment",
        epochs=args.epochs,
        patience=args.patience,
        batch=args.batch,
        imgsz=args.imgsz,
        device=device,
        seed=args.seed,
        project=str(EXPERIMENTS),
        name=args.name,
        exist_ok=True,
        resume=args.resume,
        amp=True,
        cache=False,          # 4 GB VRAM: cache=True is how OOM happens at epoch 30
        workers=0,            # Windows: worker respawn per epoch is the slow and
                              # crash-prone path, and 13 iters/epoch gains nothing
                              # from it. Every prior run used workers=0.
        degrees=0.0,          # NOT a free choice -- see the module docstring
        fliplr=0.5,
        flipud=0.5,
        close_mosaic=50,   # last 50 epochs mosaic-free. Raised from 15 when the
                           # budget went to 1000 epochs: 15 would have been 1.5%
                           # of the run, too short to settle on undistorted frames.
        val=True,
        plots=True,
    )

    metrics = model.val(data=args.data, split="test", imgsz=args.imgsz,
                        batch=args.batch, device=device, workers=0,
                        project=str(EXPERIMENTS), name=f"{args.name}-test", exist_ok=True)

    (out_dir / "provenance.json").write_text(json.dumps({
        "run": args.name,
        "task": "segment",
        "classes": ["ghost_net"],
        "weights_init": str(args.weights),
        "data": str(args.data),
        "seed": args.seed,
        "epochs": args.epochs,
        "batch": args.batch,
        "imgsz": args.imgsz,
        "device": str(device),
        "git_commit": git_commit(),
        "cli": " ".join(sys.argv),
        "caveat": ("test split is 11 chips -- upper bound only. NOT comparable with gv5 mAP50: "
                   "different task, label geometry and metric. Report under Tier 1 of "
                   "EXPERIMENT_GV7_PLAN.md 10.5 as a review candidate, never a detection claim."),
    }, indent=2), encoding="utf-8")

    print(f"\nwrote {out_dir / 'provenance.json'}")
    print("Remember: 11 test chips. Quote the bound, not the point estimate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
