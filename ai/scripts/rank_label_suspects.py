"""Rank labelled boxes by how likely they are to be WRONG, so an audit can start.

    python ai/scripts/rank_label_suspects.py --class wreck
    python ai/scripts/rank_label_suspects.py --class wreck --render 150

gv7.1 in EXPERIMENT_GV7_PLAN.md is "label audit applied to train/val only", on
the suspicion (§2) that `wreck` at precision 0.42 smells of label noise. The
audit has never started because it reads as 1,373 boxes of human work with no
way in.

A mechanical scan found nothing: zero duplicates, zero out-of-bounds, zero
degenerate boxes across all 13,896 training frames. So the errors, if they
exist, are *semantic* -- boxes drawn around the wrong thing, drawn too loosely,
or missing entirely -- and only a human can adjudicate those. What a script can
do is decide the ORDER, so the first hour of review is spent on the boxes most
likely to be wrong rather than on a random 5%.

The circularity, stated plainly
-------------------------------
This ranks labels by disagreement with a model that was TRAINED ON THOSE
LABELS. That is genuinely circular and the ranking must not be read as a
verdict:

* a box the model misses may be a bad label OR a real model failure, and this
  cannot tell them apart;
* an error the model learned faithfully will not be flagged at all, because the
  model agrees with it.

So this is a triage ORDER, not a defect list. Every row is a question for a
human, and "the label was right, the model is wrong" is a valid and expected
answer -- worth recording, because a pile of those is evidence about the model
rather than the labels.

The test split is never included
--------------------------------
§3.1: auditing train/val while test keeps its errors means measuring a better
model with a worse ruler, and silently auditing test destroys comparability
with gv1-gv6. Corrections must reach `ai/data/interim/`, which is shared by all
three splits, so this emits a manifest that maps each reviewable frame back to
its interim source **and refuses to list any source file whose image lands in
test**. SCTD matters here: it splits `mode: random`, and 50 of its frames are in
test.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "ai" / "data" / "processed"
INTERIM = ROOT / "ai" / "data" / "interim"
ANNOTATE = ROOT / "ai" / "data" / "annotate"
WEIGHTS = ROOT / "ai" / "models" / "trained" / "ghostnet.pt"

CLASSES = {"wreck": 0, "plane": 1, "debris": 2, "ghost_pot": 3, "ghost_net": 4}


def read_labels(path: Path) -> list[tuple[int, float, float, float, float]]:
    out = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        p = line.split()
        if len(p) == 5:
            out.append((int(p[0]), *(float(v) for v in p[1:])))
    return out


def to_corners(b: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    x, y, w, h = b
    return (x - w / 2, y - h / 2, x + w / 2, y + h / 2)


def iou(a, b) -> float:
    ax0, ay0, ax1, ay1 = to_corners(a)
    bx0, by0, bx1, by1 = to_corners(b)
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    union = (ax1 - ax0) * (ay1 - ay0) + (bx1 - bx0) * (by1 - by0) - inter
    return inter / union if union > 0 else 0.0


def interim_source(stem: str) -> tuple[str, str] | None:
    """`AI4SHIPWRECKS__DM_Wilson_01__x0_y0` -> ('AI4SHIPWRECKS', 'DM_Wilson_01__x0_y0')."""
    if "__" not in stem:
        return None
    source, rest = stem.split("__", 1)
    return source, rest


def test_stems() -> set[str]:
    d = PROCESSED / "test" / "images"
    return {p.stem for p in d.iterdir()} if d.is_dir() else set()


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--class", dest="cls", default="wreck", choices=sorted(CLASSES))
    ap.add_argument("--weights", default=str(WEIGHTS))
    ap.add_argument("--splits", nargs="+", default=["train", "val"],
                    choices=["train", "val"],
                    help="test is not offered on purpose -- see the docstring")
    ap.add_argument("--conf", type=float, default=0.05,
                    help="low, so 'the model saw nothing at all here' means something")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--device", default="cpu", help="722 frames; cpu keeps the GPU free")
    ap.add_argument("--render", type=int, default=0,
                    help="write overlay sheets for the top N findings")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cls_id = CLASSES[args.cls]
    out_dir = Path(args.out) if args.out else ANNOTATE / f"{args.cls}_audit"
    out_dir.mkdir(parents=True, exist_ok=True)

    in_test = test_stems()

    # Which frames carry this class at all. Everything else is irrelevant to the
    # audit and running the model over 13,896 frames to discover that is waste.
    targets: list[tuple[str, Path, Path]] = []
    for split in args.splits:
        lab_dir = PROCESSED / split / "labels"
        img_dir = PROCESSED / split / "images"
        for lab in lab_dir.glob("*.txt"):
            rows = read_labels(lab)
            if any(r[0] == cls_id for r in rows):
                img = next((img_dir / f"{lab.stem}{e}"
                            for e in (".png", ".jpg", ".jpeg")
                            if (img_dir / f"{lab.stem}{e}").exists()), None)
                if img:
                    targets.append((split, img, lab))

    print(f"  {args.cls}: {len(targets)} frames carry the class in {'+'.join(args.splits)}")
    if not targets:
        return 1

    from ultralytics import YOLO
    model = YOLO(args.weights)

    findings: list[dict] = []
    for split, img, lab in targets:
        gt = [r for r in read_labels(lab) if r[0] == cls_id]
        res = model.predict(str(img), imgsz=args.imgsz, device=args.device,
                            conf=args.conf, verbose=False)[0]
        preds = []
        if res.boxes is not None and len(res.boxes):
            for b, c, s in zip(res.boxes.xywhn.tolist(),
                               res.boxes.cls.tolist(),
                               res.boxes.conf.tolist()):
                preds.append((int(c), tuple(b), float(s)))

        same = [p for p in preds if p[0] == cls_id]
        matched_preds: set[int] = set()

        for g in gt:
            gbox = g[1:]
            best_i, best_iou = -1, 0.0
            for i, p in enumerate(same):
                v = iou(gbox, p[1])
                if v > best_iou:
                    best_i, best_iou = i, v
            # Best-overlapping prediction of ANY class, for the conflict test.
            other, other_iou = None, 0.0
            for p in preds:
                if p[0] == cls_id:
                    continue
                v = iou(gbox, p[1])
                if v > other_iou:
                    other, other_iou = p, v

            if best_iou < 0.10:
                if other is not None and other_iou >= 0.30:
                    kind, score = "class_conflict", 0.80 + 0.20 * other[2]
                    note = f"model says {list(CLASSES)[other[0]]} @ {other[2]:.2f}"
                else:
                    kind, score = "orphan_label", 0.70
                    note = "no prediction of this class overlaps the box"
            elif best_iou < 0.50:
                kind, score = "loose_box", 0.30 + (0.50 - best_iou)
                note = f"best IoU {best_iou:.2f} against a prediction"
            else:
                continue  # model and label agree; nothing to ask a human

            if best_i >= 0:
                matched_preds.add(best_i)
            findings.append({
                "score": round(score, 4), "kind": kind, "split": split,
                "frame": img.stem, "box": " ".join(f"{v:.5f}" for v in gbox),
                "note": note,
            })

        for i, p in enumerate(same):
            if i in matched_preds or p[2] < 0.50:
                continue
            if max((iou(g[1:], p[1]) for g in gt), default=0.0) < 0.10:
                findings.append({
                    "score": round(0.40 + 0.40 * p[2], 4), "kind": "missing_label",
                    "split": split, "frame": img.stem,
                    "box": " ".join(f"{v:.5f}" for v in p[1]),
                    "note": f"confident prediction @ {p[2]:.2f} with no label here",
                })

    findings.sort(key=lambda f: -f["score"])

    queue = out_dir / "queue.csv"
    with queue.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["rank", "score", "kind", "split", "frame",
                                           "box", "note", "verdict", "reviewer"])
        w.writeheader()
        for i, f in enumerate(findings, 1):
            # verdict/reviewer are left EMPTY on purpose: the reviewer fills them
            # in, and an unfilled row is visibly unreviewed rather than assumed.
            w.writerow({"rank": i, **f, "verdict": "", "reviewer": ""})

    # Manifest: where a correction has to be written, with the test guard.
    frames = sorted({f["frame"] for f in findings})
    manifest, blocked = {}, []
    for stem in frames:
        if stem in in_test:
            blocked.append(stem)
            continue
        src = interim_source(stem)
        if not src:
            continue
        source, rest = src
        # Two interim layouts exist. Sources with a fixed upstream split keep
        # their split directories (AI4SHIPWRECKS/train/labels/); sources we
        # split ourselves are flat (SCTD/labels/), because there was no upstream
        # split to preserve. Check both rather than assume the common one.
        candidates = [INTERIM / source / d / "labels" / f"{rest}.txt"
                      for d in ("train", "val", "test", "valid")]
        candidates.append(INTERIM / source / "labels" / f"{rest}.txt")
        for cand in candidates:
            if cand.exists():
                manifest[stem] = str(cand.relative_to(ROOT))
                break

    (out_dir / "manifest.json").write_text(json.dumps({
        "class": args.cls,
        "splits_audited": args.splits,
        "frames": len(frames),
        "findings": len(findings),
        "interim_targets": manifest,
        "refused_because_in_test": blocked,
        "rule": ("Corrections are written to the interim label file, never to "
                 "ai/data/processed/ (rebuilt in place) and never to a frame in "
                 "the test split (EXPERIMENT_GV7_PLAN.md 3.1)."),
    }, indent=2), encoding="utf-8")

    from collections import Counter
    kinds = Counter(f["kind"] for f in findings)
    print(f"\n  {len(findings)} findings over {len(frames)} frames")
    for k, n in kinds.most_common():
        print(f"    {k:16s} {n}")
    print(f"\n  queue     {queue.relative_to(ROOT)}")
    print(f"  manifest  {(out_dir / 'manifest.json').relative_to(ROOT)}")
    if blocked:
        print(f"  refused   {len(blocked)} frames are in the TEST split and are excluded")

    if args.render:
        render(findings[:args.render], out_dir / "_review")
    else:
        print("\n  --render N writes overlay sheets for the top N.")
    print("\n  This is a triage ORDER, not a defect list. 'Label right, model wrong'")
    print("  is a valid verdict and worth recording.")
    return 0


def render(findings: list[dict], out: Path) -> None:
    """Overlay each flagged box on its frame, so review is looking not reading."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("  (Pillow not available; skipping render)")
        return
    out.mkdir(parents=True, exist_ok=True)
    for i, f in enumerate(findings, 1):
        img_path = next((PROCESSED / f["split"] / "images" / f"{f['frame']}{e}"
                         for e in (".png", ".jpg", ".jpeg")
                         if (PROCESSED / f["split"] / "images" / f"{f['frame']}{e}").exists()), None)
        if not img_path:
            continue
        im = Image.open(img_path).convert("RGB")
        W, H = im.size
        d = ImageDraw.Draw(im)
        x, y, w, h = (float(v) for v in f["box"].split())
        d.rectangle([(x - w / 2) * W, (y - h / 2) * H, (x + w / 2) * W, (y + h / 2) * H],
                    outline=(255, 64, 64), width=3)
        d.text((4, 4), f"#{i} {f['kind']}  {f['note']}", fill=(255, 255, 0))
        im.save(out / f"{i:04d}_{f['kind']}_{f['frame']}.png")
    print(f"  rendered  {len(findings)} sheets -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    raise SystemExit(main())
