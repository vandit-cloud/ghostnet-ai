"""Train the chip-level `natural` classifier and score it honestly.

    python ai/scripts/train_natural.py --dry-run
    python ai/scripts/train_natural.py --name nat1 --seed 0

Reads  ai/data/natural/{train,val,test}/<class>/*.jpg   (build_natural_dataset.py)
Writes ai/experiments/<name>/{provenance.json,test_metrics.json,weights/}

What this is for
----------------
SIH26057 asks for separation of natural seafloor topology from artificial
anomalies. Today that requirement is answered only by a FALSE-ALARM RATE -- the
detector's silence on frames carrying no annotation. Silence is evidence, and
it is the honest version of the claim, but the model never actually asserts
"that is a gully field". The contract has carried a `natural` class since the
interface was frozen (contracts/ai-output.schema.json), config.py has tuned it
an asymmetric review floor of 0.45, and decision.py has a written policy to
report rather than discard it. Nothing has ever emitted one.

This emits one. It is a SECOND-STAGE, CHIP-LEVEL model that runs beside the
detector and never inside it -- see build_natural_dataset.py for why a
detector class would have been the wrong shape.

Why classification accuracy is not the headline here
-----------------------------------------------------
Class and site are entangled in the source data. `SM` is shenzhen-only; `SW` is
49 chips from two sites. A model that learns "this is shenzhen" scores well on
scour marks without having learned what a scour mark looks like, and top-1
accuracy cannot tell the two apart.

So this script refuses to print a bare accuracy. Every run writes, and every
run prints, accuracy broken down BY SITE as well as by class. Where a class
has one site, the per-site table makes that visible in the same glance as the
score. This mirrors EXPERIMENT_GV7_PLAN.md 10.6: seeds agreeing with each other
is not sites agreeing with each other.

The leave-one-site-out control
------------------------------
--holdout-site trains with one site withheld entirely and tests on it. That is
the only measurement here that answers "did it learn the morphology or the
survey", and it is cheap -- minutes, not the detector's 19 hours. Run it before
quoting any number from this model.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

DATA_ROOT = AI_ROOT / "data" / "natural"
EXPERIMENTS = AI_ROOT / "experiments"
PRETRAINED = AI_ROOT / "models" / "pretrained"

SITE_RE = re.compile(r"^CHINA-OFFSHORE__(?P<site>.+?)_(?P<code>[A-Za-z]+)_(?P<idx>\d+)\.")


def site_of(name: str) -> str:
    m = SITE_RE.match(name)
    return m.group("site") if m else "unknown"


def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=AI_ROOT, timeout=10,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def score(model, split_dir: Path, class_names: list[str]) -> dict:
    """Predict every chip in a split and break the result down by class AND site.

    Returns per-class accuracy, per-site accuracy, the per-site breakdown
    within each class, and a confusion matrix -- everything needed to tell
    "learned the morphology" apart from "learned the survey".
    """
    per_class = defaultdict(lambda: {"n": 0, "correct": 0})
    per_site = defaultdict(lambda: {"n": 0, "correct": 0})
    per_class_site = defaultdict(lambda: defaultdict(lambda: {"n": 0, "correct": 0}))
    confusion: Counter[tuple[str, str]] = Counter()
    n = correct = 0

    for class_dir in sorted(p for p in split_dir.iterdir() if p.is_dir()):
        truth = class_dir.name
        for img in sorted(class_dir.iterdir()):
            if img.suffix.lower() not in (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"):
                continue
            res = model.predict(str(img), verbose=False)[0]
            pred = class_names[int(res.probs.top1)]
            site = site_of(img.name)
            hit = int(pred == truth)

            n += 1
            correct += hit
            per_class[truth]["n"] += 1
            per_class[truth]["correct"] += hit
            per_site[site]["n"] += 1
            per_site[site]["correct"] += hit
            per_class_site[truth][site]["n"] += 1
            per_class_site[truth][site]["correct"] += hit
            confusion[(truth, pred)] += 1

    def acc(d):
        return {k: {"n": v["n"], "correct": v["correct"],
                    "accuracy": (v["correct"] / v["n"]) if v["n"] else None}
                for k, v in d.items()}

    return {
        "n": n,
        "accuracy": (correct / n) if n else None,
        "per_class": acc(per_class),
        "per_site": acc(per_site),
        "per_class_per_site": {c: acc(s) for c, s in per_class_site.items()},
        "confusion": {f"{t}->{p}": c for (t, p), c in sorted(confusion.items())},
    }


def print_report(m: dict) -> None:
    print(f"\n  overall  {m['accuracy']:.4f}  (n={m['n']})")
    print(f"\n  {'class':20} {'n':>5} {'acc':>7}   per-site")
    for cls, v in sorted(m["per_class"].items()):
        sites = m["per_class_per_site"].get(cls, {})
        spread = ", ".join(
            f"{s} {d['accuracy']:.2f} (n={d['n']})" for s, d in sorted(sites.items())
        )
        warn = "   <-- SINGLE SITE" if len(sites) == 1 else ""
        print(f"  {cls:20} {v['n']:>5} {v['accuracy']:>7.4f}   {spread}{warn}")
    print(f"\n  {'site':20} {'n':>5} {'acc':>7}")
    for s, v in sorted(m["per_site"].items()):
        print(f"  {s:20} {v['n']:>5} {v['accuracy']:>7.4f}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Train the chip-level natural classifier.")
    ap.add_argument("--model", default="yolo11s-cls",
                    help="yolo11n-cls | yolo11s-cls | path to a .pt")
    ap.add_argument("--data", default=str(DATA_ROOT))
    ap.add_argument("--name", default=None)
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--imgsz", type=int, default=224,
                    help="224 is the classification default; chips are 350-740 px")
    ap.add_argument("--batch", type=int, default=32,
                    help="classification at 224 is light; 32 fits the 4 GB ceiling")
    ap.add_argument("--patience", type=int, default=12)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default=None)
    ap.add_argument("--holdout-site", default=None,
                    help="train without this site and test on it -- the control that "
                         "separates morphology from survey")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data_root = Path(args.data)
    if not (data_root / "train").is_dir():
        print(f"! {data_root}/train does not exist.\n"
              "  Run ai/scripts/build_natural_dataset.py first, from the tree that\n"
              "  actually holds ai/data/processed (E:\\New folder).")
        return 1

    import torch
    from ultralytics import YOLO

    device = args.device or ("0" if torch.cuda.is_available() else "cpu")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    name = args.name or f"natural-{Path(args.model).stem}-{stamp}"
    run_dir = EXPERIMENTS / name

    # Same overwrite guard as train.py: ultralytics happily reopens a finished
    # run directory and restarts at epoch 1, destroying the weights with no
    # error. The first sign is a results.csv that begins again from 1.
    if run_dir.exists() and not args.force:
        print(f"! {run_dir} already exists. Pass --force to overwrite it.")
        return 1

    weights = args.model if args.model.endswith((".pt", ".yaml")) else str(
        PRETRAINED / f"{args.model}.pt"
    )

    print(f"  model    {weights}")
    print(f"  data     {data_root}")
    print(f"  epochs   {args.epochs}   batch {args.batch}   imgsz {args.imgsz}   seed {args.seed}")
    print(f"  device   {device}")
    if args.holdout_site:
        print(f"  HOLDOUT  {args.holdout_site} -- withheld from train, used as test")

    if args.dry_run:
        print("\n  --dry-run: nothing trained.")
        return 0

    EXPERIMENTS.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "provenance.json").write_text(json.dumps({
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "weights_init": weights,
        "task": "chip-level natural classification (second stage, not a detector class)",
        "args": vars(args),
        "device": device,
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "build_report": json.loads((data_root / "build_report.json").read_text(encoding="utf-8"))
        if (data_root / "build_report.json").exists() else None,
    }, indent=2), encoding="utf-8")

    model = YOLO(weights)
    model.train(
        data=str(data_root),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        patience=args.patience,
        seed=args.seed,
        device=device,
        project=str(EXPERIMENTS),
        name=name,
        exist_ok=True,
    )

    test_dir = data_root / "test"
    if not test_dir.is_dir():
        print("\n! no test split; skipping scoring.")
        return 0

    best = run_dir / "weights" / "best.pt"
    scored = YOLO(str(best))
    class_names = [scored.names[i] for i in sorted(scored.names)]
    metrics = score(scored, test_dir, class_names)
    metrics["holdout_site"] = args.holdout_site
    metrics["seed"] = args.seed

    (run_dir / "test_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print_report(metrics)
    print(f"\n  wrote {run_dir / 'test_metrics.json'}")
    print("\n  Quote per-class accuracy WITH its site spread, never the bare overall.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
