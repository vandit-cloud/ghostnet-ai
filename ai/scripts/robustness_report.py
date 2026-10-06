"""When does the detector stop being trustworthy? Re-score the held-out test
split under controlled degradations, on the same ruler as every other run.

    python ai/scripts/robustness_report.py --data "E:/New folder/ai/data/processed/data.yaml"
    python ai/scripts/robustness_report.py --data ... --limit 60 --conditions clean,speckle_0.35   # smoke

Writes ai/experiments/robustness/robustness_metrics.json and REPORT.md.

Why this exists
---------------
Every number the project quotes is measured on clean frames. A survey is not
clean: speckle, a gain setting that flattens contrast, a towfish that loses
pings. The only degradation curve on record was taken on ONE tile by an outside
review ("collapses to zero at speckle sigma 0.35"), and a later 109-frame count
contradicted it. This replaces both with the full 4,346-frame test split, scored
two ways per condition:

* **mAP / recall** from Ultralytics `.val()`, called exactly as `evaluate.py`
  calls it (imgsz 640, batch 4, default conf and IoU), so the clean row must
  reproduce gv5's recorded test result. If it does not, the harness is wrong
  and no other row means anything.
* **False alarms on seabed carrying no annotation**, the share of the split's
  background tiles with at least one box at the shipped raw gate 0.10, exactly
  as `evaluate_background.py` counts it. The clean row must reproduce 7.82%.

A degradation that lowers recall is expected. One that RAISES the false-alarm
rate is the dangerous kind: the system gets louder as it gets less able to see.

The degradations
----------------
Each is deterministic (seeded per image from its file name), so a rerun is
byte-identical. None of them is claimed to be the physics of a real sonar; each
is a named, reproducible stress.

* `speckle_S`  -- multiplicative unit-mean gamma noise with standard deviation S,
  the standard fully-developed-speckle model (shape 1/S^2, scale S^2). The
  single-tile review never recorded its noise model, so its "sigma 0.35" is not
  necessarily this one.
* `contrast_C` -- intensities pulled toward the frame mean by factor C: a gain
  or TVG setting that flattens the returns.
* `blur_K`     -- Gaussian blur with a K x K kernel: along-track smear, or a
  resolution well below what the detector trained on.
* `dropout_P`  -- bursts of 4-16 zeroed rows until P% of rows are lost: missing
  pings. `ghostnet.dropout` exists to flag exactly this.

Not measured, and why: range-dependent (near/far) behaviour. Test tiles come
from ten sources and most carry no nadir position, so "far range" cannot be
defined per box without guessing.

Degraded copies are written to a work directory one condition at a time and
deleted after scoring (`--keep` to keep them). The clean condition scores the
original split in place, never a re-encoded copy.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS = ROOT / "ai" / "experiments"
OUT_DIR = EXPERIMENTS / "robustness"
DATA_YAML = ROOT / "ai" / "data" / "processed" / "data.yaml"
WEIGHTS = ROOT / "ai" / "models" / "trained" / "ghostnet.pt"

RAW_GATE = 0.10          # config.raw_conf_threshold: the shipped detector gate
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}

# gv5's recorded clean result on the frozen ruler, which the clean row must
# reproduce (ai/experiments/gv5-yolo11s/test_metrics.json and
# background_metrics.json). Checked only on a full, unlimited run.
EXPECTED_CLEAN = {"map50": 0.3525, "bg_rate": 0.0782}


# --- degradations -------------------------------------------------------------


def _speckle(sigma: float):
    def apply(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        shape = img.shape[:2]
        noise = rng.gamma(1.0 / sigma**2, sigma**2, size=shape).astype(np.float32)
        if img.ndim == 3:
            noise = noise[..., None]
        return img.astype(np.float32) * noise
    return apply


def _contrast(factor: float):
    def apply(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        f = img.astype(np.float32)
        mean = f.mean(axis=(0, 1), keepdims=True)
        return mean + (f - mean) * factor
    return apply


def _blur(kernel: int):
    def apply(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        return cv2.GaussianBlur(img, (kernel, kernel), 0).astype(np.float32)
    return apply


def _dropout(percent: float):
    def apply(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        out = img.astype(np.float32).copy()
        rows = img.shape[0]
        target = int(round(rows * percent / 100.0))
        lost = np.zeros(rows, dtype=bool)
        while lost.sum() < target:
            start = int(rng.integers(0, rows))
            lost[start:start + int(rng.integers(4, 17))] = True
        out[lost] = 0.0
        return out
    return apply


CONDITIONS = {
    "clean": None,
    "speckle_0.20": _speckle(0.20),
    "speckle_0.35": _speckle(0.35),
    "speckle_0.50": _speckle(0.50),
    "contrast_0.50": _contrast(0.50),
    "contrast_0.25": _contrast(0.25),
    "blur_9": _blur(9),
    "blur_21": _blur(21),
    "dropout_10": _dropout(10),
}


# --- helpers ------------------------------------------------------------------


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def load_yaml(path: Path) -> dict:
    import yaml
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def split_dir(data: dict, data_yaml: Path) -> Path:
    base = Path(data.get("path") or data_yaml.parent)
    if not base.is_absolute():
        base = (data_yaml.parent / base).resolve()
    return base / Path(data["test"]).parent  # ".../test" from "test/images"


def list_images(images: Path, limit: int | None) -> list[Path]:
    """The split, or an evenly spaced sample of it: files sort by source, so the
    first N would all come from one survey."""
    files = sorted(p for p in images.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    if not limit or limit >= len(files):
        return files
    step = len(files) / limit
    return [files[int(i * step)] for i in range(limit)]


def show(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def is_background(labels: Path, image: Path) -> bool:
    txt = labels / (image.stem + ".txt")
    return txt.exists() and not txt.read_text(encoding="utf-8").strip()


def degrade_split(images: list[Path], labels: Path, fn, cond_idx: int, dest: Path) -> None:
    """Write a degraded copy of `images` (and their labels) under dest/."""
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "images").mkdir(parents=True)
    (dest / "labels").mkdir(parents=True)
    for i, src in enumerate(images):
        img = cv2.imread(str(src), cv2.IMREAD_UNCHANGED)
        if img is None:
            raise RuntimeError(f"unreadable image: {src}")
        if img.dtype != np.uint8:
            raise RuntimeError(f"{src.name} is {img.dtype}; the degradations assume 8-bit frames")
        alpha = None
        if img.ndim == 3 and img.shape[2] == 4:
            img, alpha = img[..., :3], img[..., 3:]
        seed = zlib.crc32(src.name.encode("utf-8")) ^ (cond_idx * 0x9E3779B1 & 0xFFFFFFFF)
        out = np.clip(fn(img, np.random.default_rng(seed)), 0, 255).astype(np.uint8)
        if alpha is not None:
            out = np.concatenate([out, alpha], axis=2)
        params = [cv2.IMWRITE_JPEG_QUALITY, 100] if src.suffix.lower() in {".jpg", ".jpeg"} else []
        if not cv2.imwrite(str(dest / "images" / src.name), out, params):
            raise RuntimeError(f"could not write {dest / 'images' / src.name}")
        label = labels / (src.stem + ".txt")
        if label.exists():
            shutil.copyfile(label, dest / "labels" / label.name)
        if (i + 1) % 250 == 0 or i + 1 == len(images):
            print(f"    degraded {i + 1}/{len(images)}", end="\r")
    print()


def write_yaml(path: Path, split_root: Path, names) -> None:
    import yaml
    path.write_text(yaml.safe_dump({"path": str(split_root), "train": "images", "val": "images",
                                    "test": "images", "names": names}), encoding="utf-8")


def summarise(metrics) -> dict:
    box = metrics.box
    names = getattr(metrics, "names", {}) or {}
    per_class = {}
    for i, c in enumerate(getattr(box, "ap_class_index", [])):
        per_class[str(names.get(int(c), int(c)))] = {
            "map50": float(box.ap50[i]), "recall": float(box.r[i]), "precision": float(box.p[i])}
    return {"map50": float(box.map50), "map50_95": float(box.map), "precision": float(box.mp),
            "recall": float(box.mr), "per_class": per_class}


def background_rate(model, images: list[Path], imgsz: int, device) -> dict:
    flagged, boxes = 0, 0
    for i in range(0, len(images), 32):
        chunk = [str(p) for p in images[i:i + 32]]
        for res in model.predict(source=chunk, imgsz=imgsz, conf=RAW_GATE, device=device, verbose=False):
            n = len(res.boxes) if res.boxes is not None else 0
            flagged += n > 0
            boxes += n
    total = len(images)
    return {"tiles": total, "flagged": flagged, "boxes": boxes, "rate": flagged / total if total else None}


# --- report -------------------------------------------------------------------


def _pct(x) -> str:
    return "—" if x is None else f"{x * 100:.2f}%"


def write_report(result: dict, path: Path) -> None:
    rows = result["conditions"]
    clean = rows.get("clean")
    classes = list(clean["val"]["per_class"]) if clean else []
    lines = [
        "# Robustness report",
        "",
        f"Generated {result['created_utc'][:16]} UTC by `ai/scripts/robustness_report.py` "
        f"(commit `{result['git_commit'][:7]}`). Weights `{Path(result['weights']).name}` "
        f"({result.get('model_version') or 'unknown'}); test split `{result.get('dataset_version')}`, "
        f"{result['n_images']} images, {result['n_background']} carrying no annotation.",
        "",
    ]
    if result["limited"]:
        lines += ["> **Smoke run** (`--limit`): a subset of the split. Not comparable with any "
                  "recorded result; do not quote.", ""]
    if result.get("reproduction"):
        lines += [f"Harness check, clean row against gv5's record: {result['reproduction']}", ""]

    lines += [
        "| condition | mAP50 | Δ | recall | Δ | " + " | ".join(f"{c} R" for c in classes)
        + " | empty-seabed false alarms @ raw 0.10 | Δ |",
        "|" + "---|" * (5 + len(classes) + 2),
    ]
    for name, r in rows.items():
        v, bg = r["val"], r["background"]
        d_map = "" if not clean else f"{v['map50'] - clean['val']['map50']:+.3f}"
        d_rec = "" if not clean else f"{v['recall'] - clean['val']['recall']:+.3f}"
        d_bg = "" if not clean or bg["rate"] is None else f"{(bg['rate'] - clean['background']['rate']) * 100:+.2f} pp"
        per = " | ".join(f"{v['per_class'].get(c, {}).get('recall', float('nan')):.3f}" for c in classes)
        lines.append(f"| `{name}` | {v['map50']:.3f} | {d_map} | {v['recall']:.3f} | {d_rec} | {per} | "
                     f"{_pct(bg['rate'])} ({bg['flagged']}/{bg['tiles']}) | {d_bg} |")

    lines += [
        "",
        "Per-class recall is Ultralytics' at its default operating point. `plane` has 9 test "
        "boxes and `ghost_net` 36: do not read a trend off either.",
        "",
        "## Recorded clean-data evidence, for the same table",
        "",
    ]
    for item in result.get("recorded", []):
        lines.append(f"- {item}")
    lines += ["", "Degradations, seeds and what is not measured: see the module docstring.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def recorded_evidence() -> list[str]:
    out = []
    bg = EXPERIMENTS / "gv5-yolo11s" / "background_metrics.json"
    if bg.exists():
        row = next((r for r in json.loads(bg.read_text())["curve"] if abs(r["threshold"] - RAW_GATE) < 1e-9), None)
        if row:
            out.append(f"Empty-seabed false alarms, clean, raw gate 0.10: {row['rate'] * 100:.2f}% "
                       f"({row['frames_flagged']} tiles) — `{bg.relative_to(ROOT).as_posix()}`")
    size = EXPERIMENTS / "gv5-yolo11s" / "wreck_recall_by_size.json"
    if size.exists():
        bands = json.loads(size.read_text())["bands"]
        out.append("Wreck recall by share of frame: " + ", ".join(
            f"{k} {v['recall']:.3f} ({v['found']}/{v['total']})" for k, v in bands.items())
            + f" — `{size.relative_to(ROOT).as_posix()}`")
    unet = EXPERIMENTS / "unet-scoring" / "RESULTS.md"
    if unet.exists():
        out.append("ghost_net U-Net (gvU1n, 3 seeds): fires on 1.3% of empty seabed chips, on "
                   "China-Offshore only; 11 test chips — `ai/experiments/unet-scoring/RESULTS.md`. "
                   "Not re-measured under degradation here: 11 chips cannot carry a curve.")
    return out


# --- main ---------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weights", default=str(WEIGHTS))
    ap.add_argument("--data", default=str(DATA_YAML))
    ap.add_argument("--conditions", default=",".join(CONDITIONS),
                    help=f"comma-separated subset of: {', '.join(CONDITIONS)}")
    ap.add_argument("--work", default=None,
                    help="where degraded copies go (default: <data root>/../interim/robustness)")
    ap.add_argument("--out", default=str(OUT_DIR))
    ap.add_argument("--limit", type=int, default=None, help="an evenly spaced N-image sample (smoke run)")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=4, help="4 matches evaluate.py / train.py")
    ap.add_argument("--device", default=None)
    ap.add_argument("--keep", action="store_true", help="keep degraded copies")
    args = ap.parse_args()

    wanted = [c.strip() for c in args.conditions.split(",") if c.strip()]
    unknown = [c for c in wanted if c not in CONDITIONS]
    if unknown:
        print(f"unknown condition(s): {', '.join(unknown)}")
        return 1

    weights, data_yaml = Path(args.weights), Path(args.data)
    for p in (weights, data_yaml):
        if not p.exists():
            print(f"not found: {p}")
            return 1

    import torch
    from ultralytics import YOLO
    from _fingerprint import check_test_split

    data = load_yaml(data_yaml)
    test_root = split_dir(data, data_yaml)
    images_dir, labels_dir = test_root / "images", test_root / "labels"
    ok, drift = check_test_split(data_yaml.parent)
    if not ok:
        print("! DATASET DRIFT -- the test split is not the frozen ruler:")
        for problem in drift:
            print(f"    {problem}")
        return 1

    images = list_images(images_dir, args.limit)
    background = [p for p in images if is_background(labels_dir, p)]
    build = json.loads((data_yaml.parent / "build_report.json").read_text())
    work = Path(args.work) if args.work else data_yaml.parent.parent / "interim" / "robustness"
    device = args.device if args.device is not None else (0 if torch.cuda.is_available() else "cpu")
    sidecar = weights.with_suffix(".json")
    model_version = json.loads(sidecar.read_text()).get("model_version") if sidecar.exists() else None

    print(f"\n  weights    {weights} ({model_version})")
    print(f"  test split {test_root}  ({len(images)} images, {len(background)} background)")
    print(f"  work dir   {work}")
    print(f"  conditions {', '.join(wanted)}\n")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(weights))
    result = {
        "created_utc": datetime.now(timezone.utc).isoformat(), "git_commit": git_commit(),
        "weights": str(weights), "model_version": model_version,
        "dataset_version": build.get("dataset_version"), "n_images": len(images),
        "n_background": len(background), "limited": args.limit is not None,
        "val_kwargs": {"imgsz": args.imgsz, "batch": args.batch, "conf": "default", "iou": "default"},
        "raw_gate": RAW_GATE, "conditions": {},
    }

    for idx, name in enumerate(CONDITIONS):
        if name not in wanted:
            continue
        print(f"== {name}")
        fn = CONDITIONS[name]
        if fn is None and args.limit is None:
            split_root, bg_images = test_root, background
            yaml_path = data_yaml
            split = "test"
        else:
            split_root = work / name
            if fn is None:  # a limited clean run still needs a subset directory
                split_root.mkdir(parents=True, exist_ok=True)
                (split_root / "images").mkdir(exist_ok=True)
                (split_root / "labels").mkdir(exist_ok=True)
                for p in images:
                    shutil.copyfile(p, split_root / "images" / p.name)
                    lab = labels_dir / (p.stem + ".txt")
                    if lab.exists():
                        shutil.copyfile(lab, split_root / "labels" / lab.name)
            else:
                degrade_split(images, labels_dir, fn, idx, split_root)
            yaml_path = work / f"{name}.yaml"
            write_yaml(yaml_path, split_root, data["names"])
            bg_images = [split_root / "images" / p.name for p in background]
            split = "test"

        metrics = model.val(data=str(yaml_path), split=split, imgsz=args.imgsz, batch=args.batch,
                            device=device, plots=False, verbose=False,
                            project=str(work / "_val"), name=name, exist_ok=True)
        row = {"val": summarise(metrics), "background": background_rate(model, bg_images, args.imgsz, device)}
        result["conditions"][name] = row
        print(f"    mAP50 {row['val']['map50']:.4f}  recall {row['val']['recall']:.4f}  "
              f"bg false alarms {_pct(row['background']['rate'])}")

        if split_root != test_root and not args.keep:
            shutil.rmtree(split_root, ignore_errors=True)
            yaml_path.unlink(missing_ok=True)
        # Written after every condition so a crash keeps what finished.
        (out_dir / "robustness_metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    clean = result["conditions"].get("clean")
    if clean and not result["limited"]:
        got_map, got_bg = clean["val"]["map50"], clean["background"]["rate"]
        good = abs(got_map - EXPECTED_CLEAN["map50"]) < 0.0015 and abs(got_bg - EXPECTED_CLEAN["bg_rate"]) < 0.0015
        result["reproduction"] = (
            f"{'REPRODUCED' if good else 'DID NOT REPRODUCE'} — mAP50 {got_map:.4f} (recorded "
            f"{EXPECTED_CLEAN['map50']}), empty-seabed rate {got_bg * 100:.2f}% (recorded "
            f"{EXPECTED_CLEAN['bg_rate'] * 100:.2f}%)")
        print(f"\n  {result['reproduction']}")
    result["recorded"] = recorded_evidence()
    (out_dir / "robustness_metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(result, out_dir / ("REPORT.md" if not result["limited"] else "REPORT.smoke.md"))
    shutil.rmtree(work / "_val", ignore_errors=True)
    print(f"\n  written: {show(out_dir)}/robustness_metrics.json and the report")
    return 0 if not clean or result["limited"] or "DID NOT" not in result.get("reproduction", "") else 2


if __name__ == "__main__":
    raise SystemExit(main())
