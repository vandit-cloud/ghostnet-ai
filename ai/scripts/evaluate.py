"""Score an EXISTING model on a held-out split, without retraining it.

Why this exists
---------------
`train.py` scores a model on the test split at the end of its own run, and
nowhere else. That is fine until the plan asks for two things it cannot do:

* **gv7.0** -- re-score the shipped gv5 on the CURRENT test split, to establish
  that the ruler still reads the same before anything is compared against it
  (EXPERIMENT_GV7_PLAN.md 3, 4.1).
* **gv7.T** -- test-time augmentation, which changes inference only. Retraining
  a model for 14 hours to measure an inference-time flag would be absurd.

Both are the same operation: load weights, run `.val()`, write the artefacts
section 5 requires. So they are one script with a flag, not two.

Comparability
-------------
The numbers this writes are only comparable with gv1-gv6 if the call matches
the one in `train.py` exactly. So `--conf` and `--iou` default to None and are
simply not passed when unset, leaving Ultralytics' own defaults in place --
which is what every previous run was scored under. Passing either makes the run
non-comparable, and the run's metrics file says so rather than leaving a reader
to notice.

The test-split fingerprint is asserted here for the same reason it is asserted
in training: a moved split makes the comparison meaningless, and it moves
silently. An eval is cheap enough that there is no excuse for skipping it.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS = ROOT / "ai" / "experiments"
DATA_YAML = ROOT / "ai" / "data" / "processed" / "data.yaml"
GV5_WEIGHTS = EXPERIMENTS / "gv5-yolo11s" / "weights" / "best.pt"


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True,
            stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def summarise(metrics) -> dict:
    """Same schema train.py writes, so the two are directly comparable.

    Extended with a `seg` block when the model has a segmentation head, because
    the net model reports mask metrics and dropping them would lose half the
    result.
    """
    out: dict = {}
    for key, head in (("box", getattr(metrics, "box", None)),
                      ("seg", getattr(metrics, "seg", None))):
        if head is None:
            continue
        block = {
            "map50": float(getattr(head, "map50", float("nan"))),
            "map50_95": float(getattr(head, "map", float("nan"))),
            "precision": float(getattr(head, "mp", float("nan"))),
            "recall": float(getattr(head, "mr", float("nan"))),
        }
        try:
            names = getattr(metrics, "names", {}) or {}
            block["per_class"] = {
                str(names.get(int(c), int(c))): {
                    "precision": float(head.p[i]),
                    "recall": float(head.r[i]),
                    "map50": float(head.ap50[i]),
                    "map50_95": float(head.ap[i]),
                }
                for i, c in enumerate(head.ap_class_index)
            }
        except Exception as exc:  # never lose the overall numbers over this
            block["per_class"] = {}
            block["per_class_error"] = repr(exc)
        out[key] = block

    # train.py writes the box numbers at the TOP level. Mirror that, so a
    # reader (or a diff) can put this file beside gv5's without a shim.
    if "box" in out:
        for k in ("map50", "map50_95", "precision", "recall", "per_class"):
            if k in out["box"]:
                out[k] = out["box"][k]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weights", default=str(GV5_WEIGHTS))
    ap.add_argument("--data", default=str(DATA_YAML))
    ap.add_argument("--split", default="test", choices=["test", "val", "train"])
    ap.add_argument("--name", default=None, help="experiment dir under ai/experiments/")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--device", default=None)
    ap.add_argument("--tta", action="store_true",
                    help="test-time augmentation (gv7.T). Inference only, no retraining.")
    ap.add_argument("--conf", type=float, default=None,
                    help="NOT comparable with gv1-gv6 if set; leave unset to match them")
    ap.add_argument("--iou", type=float, default=None,
                    help="NMS IoU. As --conf: leave unset for comparability")
    ap.add_argument("--allow-dataset-drift", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    import torch
    from ultralytics import YOLO
    from _fingerprint import check_test_split

    weights = Path(args.weights)
    if not weights.exists():
        print(f"weights not found: {weights}")
        return 1
    data_path = Path(args.data)
    if not data_path.exists():
        print(f"data yaml not found: {data_path}")
        return 1

    name = args.name or f"eval-{weights.parent.parent.name}{'-tta' if args.tta else ''}"
    device = args.device if args.device is not None else (0 if torch.cuda.is_available() else "cpu")

    splits_ok, drift = check_test_split(data_path.parent)
    if splits_ok:
        print("  dataset: test split matches build_report.json")
    else:
        print("\n! DATASET DRIFT -- this eval would not be comparable to gv1-gv6:")
        for problem in drift:
            print(f"    {problem}")
        if args.dry_run:
            print("\n  (dry run: reporting only)")
        elif not args.allow_dataset_drift:
            print("\n  Refusing to score against a moved ruler. Pass --allow-dataset-drift")
            print("  to do it anyway, and say so in notes.md.")
            return 1

    build_report = data_path.parent / "build_report.json"
    build = json.loads(build_report.read_text()) if build_report.exists() else None
    comparable = args.conf is None and args.iou is None

    print(f"\n  weights  {weights}")
    print(f"  data     {data_path}")
    print(f"  split    {args.split}   imgsz {args.imgsz}   batch {args.batch}")
    print(f"  device   {device}")
    print(f"  TTA      {'ON (augment=True)' if args.tta else 'off'}")
    if build:
        print(f"  dataset  {build.get('dataset_version', 'unknown')}")
    if not comparable:
        print("  ! --conf/--iou set: these numbers are NOT comparable with gv1-gv6")
    print(f"  output   ai/experiments/{name}\n")

    if args.dry_run:
        print("dry run: nothing evaluated.")
        return 0

    out_dir = EXPERIMENTS / name
    out_dir.mkdir(parents=True, exist_ok=True)

    kwargs = dict(data=str(data_path), split=args.split, imgsz=args.imgsz,
                  batch=args.batch, device=device, project=str(EXPERIMENTS),
                  name=f"{name}-plots", exist_ok=True, plots=True, augment=args.tta)
    if args.conf is not None:
        kwargs["conf"] = args.conf
    if args.iou is not None:
        kwargs["iou"] = args.iou

    metrics = YOLO(str(weights)).val(**kwargs)

    summary = summarise(metrics)
    summary["_eval"] = {
        "weights": str(weights),
        "split": args.split,
        "tta": bool(args.tta),
        "imgsz": args.imgsz,
        "conf": args.conf,
        "iou": args.iou,
        "comparable_with_gv1_gv6": comparable,
        "dataset_version": (build or {}).get("dataset_version"),
    }
    (out_dir / "test_metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    provenance = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "kind": "evaluation-only (no training)",
        "weights": str(weights),
        "args": vars(args),
        "device": str(device),
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "dataset_build": build,
    }
    (out_dir / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")

    for head in ("box", "seg"):
        if head not in summary:
            continue
        b = summary[head]
        print(f"\n  {args.split.upper()} [{head}]  " + "  ".join(
            f"{k}={b[k]:.4f}" for k in ("map50", "map50_95", "precision", "recall")))
        for cls, cm in b.get("per_class", {}).items():
            print(f"        {cls:12s} mAP50={cm['map50']:.4f}  P={cm['precision']:.4f}  R={cm['recall']:.4f}")

    print(f"\n  written: ai/experiments/{name}/test_metrics.json")
    print("  A run with no notes.md is not a result -- EXPERIMENT_GV7_PLAN.md 5.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
