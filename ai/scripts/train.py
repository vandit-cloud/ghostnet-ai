"""Train the detector on the merged dataset.

    python ai/scripts/train.py                      # baseline, yolo11s
    python ai/scripts/train.py --model yolo11n --epochs 30
    python ai/scripts/train.py --name exp2 --resume

Reads  ai/data/processed/data.yaml   (output of build_dataset.py)
Writes ai/experiments/<name>/        weights, curves, and a provenance record

Defaults are shaped by 4 GB of VRAM, not by what a paper would use
------------------------------------------------------------------
On an RTX 3050 Laptop the binding constraint is memory, not time. batch=4 with
AMP at 640 px fits; batch=8 does not reliably, and an out-of-memory crash three
hours into a run is the expensive kind of mistake. cache=False for the same
reason -- caching 4,200 tiles would consume RAM to save disk reads that are not
the bottleneck here.

Reproducibility is not optional
-------------------------------
Every run records the dataset build report, the git commit, the resolved
arguments and the library versions alongside the weights. A metric you cannot
regenerate is not a result, and "which dataset was that trained on?" is
unanswerable three weeks later without this.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

DATA_YAML = AI_ROOT / "data" / "processed" / "data.yaml"
EXPERIMENTS = AI_ROOT / "experiments"
PRETRAINED = AI_ROOT / "models" / "pretrained"


def git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(AI_ROOT.parent), capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser(description="Train YOLO on the merged sonar dataset.")
    ap.add_argument("--model", default="yolo11s", help="yolo11n | yolo11s | path to a .pt")
    ap.add_argument("--data", default=str(DATA_YAML))
    ap.add_argument("--name", default=None, help="experiment name (default: model + timestamp)")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=4, help="4 GB VRAM fits 4 at 640 with AMP; 8 does not")
    ap.add_argument("--patience", type=int, default=25, help="early stop after this many epochs without gain")
    ap.add_argument("--workers", type=int, default=2, help="Windows dataloader workers; high values stall")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default=None)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="print the config and check the data, train nothing")
    args = ap.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"no dataset at {data_path} -- run ai/scripts/build_dataset.py first")
        return 1

    import torch
    from ultralytics import YOLO

    device = args.device or ("0" if torch.cuda.is_available() else "cpu")
    if device == "cpu":
        print("! CUDA not available; training on CPU will take many hours.")
        print("  If this machine has an RTX 3050, the torch install is broken -- see ai/requirements.txt.")

    weights = args.model if args.model.endswith(".pt") else str(PRETRAINED / f"{args.model}.pt")
    if not Path(weights).exists():
        print(f"weights not found: {weights}")
        print("Run ai/scripts/fetch_weights.py, or pass --model with a path.")
        return 1

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    name = args.name or f"{Path(weights).stem}-{stamp}"
    EXPERIMENTS.mkdir(parents=True, exist_ok=True)

    build_report = data_path.parent / "build_report.json"
    provenance = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "weights_init": str(weights),
        "args": vars(args),
        "device": device,
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "dataset_build": json.loads(build_report.read_text()) if build_report.exists() else None,
    }

    print(f"\n  model    {weights}")
    print(f"  data     {data_path}")
    print(f"  device   {device}" + (f" ({provenance['gpu']})" if provenance["gpu"] else ""))
    print(f"  epochs   {args.epochs}   batch {args.batch}   imgsz {args.imgsz}   AMP on")
    print(f"  output   ai/experiments/{name}\n")

    if provenance["dataset_build"]:
        b = provenance["dataset_build"]
        print(f"  dataset  {b['split_sizes']}  classes {b.get('declared_classes')}")
        for w in b.get("warnings", []):
            print(f"  ! dataset warning: {w}")

    if args.dry_run:
        print("\ndry run: nothing trained.")
        return 0

    out_dir = EXPERIMENTS / name
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")

    model = YOLO(weights)
    model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=device,
        workers=args.workers,
        seed=args.seed,
        patience=args.patience,
        project=str(EXPERIMENTS),
        name=name,
        exist_ok=True,
        resume=args.resume,
        amp=True,
        cache=False,          # 4 GB of VRAM and limited RAM; disk reads are not the bottleneck
        plots=True,
        val=True,
        deterministic=True,
    )

    # Final numbers on the held-out TEST split, not the validation split the
    # model was early-stopped against. Reporting a val score as a test score is
    # the most common way a project overstates itself.
    best = out_dir / "weights" / "best.pt"
    if best.exists():
        print("\nevaluating best.pt on the held-out TEST split")
        metrics = YOLO(str(best)).val(
            data=str(data_path), split="test", imgsz=args.imgsz,
            batch=args.batch, device=device, project=str(EXPERIMENTS),
            name=f"{name}-test", exist_ok=True, plots=True,
        )
        summary = {
            "map50": float(getattr(metrics.box, "map50", float("nan"))),
            "map50_95": float(getattr(metrics.box, "map", float("nan"))),
            "precision": float(getattr(metrics.box, "mp", float("nan"))),
            "recall": float(getattr(metrics.box, "mr", float("nan"))),
        }
        (out_dir / "test_metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print("\n  TEST  " + "  ".join(f"{k}={v:.4f}" for k, v in summary.items()))
        print("\n  These are TEST numbers on a split the model never saw and was not")
        print("  early-stopped against. Quote these, never the validation figures.")

    print(f"\nweights and curves: ai/experiments/{name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
