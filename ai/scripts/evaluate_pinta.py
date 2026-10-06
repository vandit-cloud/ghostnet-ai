"""Score the shipped detector on the PINTA North Sea out-of-domain subset.

    python ai/scripts/evaluate_pinta.py
    python ai/scripts/evaluate_pinta.py --weights ai/experiments/gv8b/weights/best.pt --name gv8b

PINTA-EVAL (`build_pinta_eval.py`) is the only material we have from a sonar,
sea and contractor the model never saw. It is an EVALUATION set -- never train
on it. Of its 20 targets, 9 carry a hand-drawn `wreck` box; the other 11 are
excluded on purpose (ropes, trawl scars, and N-09-04-050 whose mark sits across
nadir from the visible wreck) and are kept as a false-alarm probe, not scored
for recall.

What it measures
----------------
Per boxed wreck, at two operating points:

* **shipped** -- the review floor a surveyor actually sees (calibrated
  confidence >= `review_floor_artificial`, net floor for ghost_net);
* **any** -- every box the detector produced, all gates off
  (`Settings.for_evaluation()`), i.e. could it EVER have found it.

A wreck counts as found when a detection reaches IoU >= 0.5 with its box
("wreck-class" requires the class to be `wreck` too; "any-class" does not --
an out-of-domain wreck called debris is still a reviewer looking at it).
`centre_hit` is the looser "a box covers the wreck centre", because these
boxes were drawn by us from the image, not by the surveyor.

On the 11 excluded frames it reports what the model raised at the shipped
floor -- on ropes and scars any report is a false alarm.

Caveats that ride with any number this prints (disclose them):
9 wrecks is a tiny n -- one wreck is 11 points; all 20 come from one
contractor and one season (N-09-03/04, 2023); pixels under the surveyor's
marker were inpainted (`inpainted_px` per record).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

EVAL_DIR = AI_ROOT / "data" / "interim" / "PINTA-EVAL"
SHIPPED_WEIGHTS = AI_ROOT / "models" / "trained" / "ghostnet.pt"  # the promoted detector the app serves
IOU_FOUND = 0.5

GREEN = (80, 200, 80)      # BGR: ground-truth box
AMBER = (0, 170, 255)      # reported at the shipped floor
BLUE = (255, 160, 0)       # below the floor


def xywh_to_xyxy(b):
    x, y, w, h = b
    return [x, y, x + w, y + h]


def iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def covers(box, pt) -> bool:
    return box[0] <= pt[0] <= box[2] and box[1] <= pt[1] <= box[3]


def detector_class(det) -> str:
    """The training class the detector produced. The contract folds wreck,
    plane and ghost_pot into `debris`; infer.py keeps the finer class only in
    the free-text notes, so a wreck-class score has to read it back from there."""
    notes = (det.get("evidence_summary") or {}).get("notes") or ""
    marker = "detector class: "
    if marker in notes:
        return notes.split(marker, 1)[1].split("|")[0].strip()
    return det["class"]


def floor_for(det, settings) -> float:
    if det["class"] == "ghost_net":
        return settings.review_floor_net
    if det["class"] == "natural":
        return settings.review_floor_natural
    return settings.review_floor_artificial


def score_target(gt, dets, settings) -> dict:
    centre = [(gt[0] + gt[2]) / 2, (gt[1] + gt[3]) / 2]
    out = {}
    for point, pool in (("any", dets),
                        ("shipped", [d for d in dets if d["calibrated_confidence"] >= floor_for(d, settings)])):
        best = max(pool, key=lambda d: iou(gt, xywh_to_xyxy(d["bbox"])), default=None)
        best_iou = iou(gt, xywh_to_xyxy(best["bbox"])) if best else 0.0
        wreck_ious = [iou(gt, xywh_to_xyxy(d["bbox"])) for d in pool if detector_class(d) == "wreck"]
        out[point] = {
            "found_any_class": best_iou >= IOU_FOUND,
            "found_wreck_class": max(wreck_ious, default=0.0) >= IOU_FOUND,
            "centre_hit": any(covers(xywh_to_xyxy(d["bbox"]), centre) for d in pool),
            "best_iou": round(best_iou, 3),
            "best_class": detector_class(best) if best else None,
            "best_conf": round(best["calibrated_confidence"], 3) if best else None,
            "n_dets": len(pool),
        }
    return out


def draw(img_path: Path, gt, dets, settings, out_path: Path) -> None:
    import cv2

    img = cv2.imread(str(img_path))
    if img is None:
        return
    if gt:
        cv2.rectangle(img, (int(gt[0]), int(gt[1])), (int(gt[2]), int(gt[3])), GREEN, 2)
    for d in dets:
        x1, y1, x2, y2 = (int(v) for v in xywh_to_xyxy(d["bbox"]))
        reported = d["calibrated_confidence"] >= floor_for(d, settings)
        colour = AMBER if reported else BLUE
        cv2.rectangle(img, (x1, y1), (x2, y2), colour, 1 if not reported else 2)
        cv2.putText(img, f'{detector_class(d)} {d["calibrated_confidence"]:.2f}', (x1, max(10, y1 - 3)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, colour, 1, cv2.LINE_AA)
    cv2.imwrite(str(out_path), img)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weights", default=str(SHIPPED_WEIGHTS))
    ap.add_argument("--name", default=None, help="output dir under ai/experiments/pinta-eval/")
    ap.add_argument("--no-images", action="store_true")
    args = ap.parse_args()

    manifest = EVAL_DIR / "manifest.jsonl"
    if not manifest.exists():
        print(f"no manifest at {manifest} -- run build_pinta_eval.py (data is gitignored)")
        return 1
    weights = Path(args.weights).expanduser().resolve()
    if not weights.exists():
        print(f"no weights at {weights}")
        return 1
    os.environ["GHOSTNET_WEIGHTS"] = str(weights)

    from ghostnet import SETTINGS, detect, warmup  # noqa: E402  (after the env var)

    if not warmup():
        print("model failed to load")
        return 1
    eval_settings = SETTINGS.for_evaluation()

    name = args.name or ("shipped" if weights == SHIPPED_WEIGHTS.resolve() else weights.parent.parent.name)
    out_dir = AI_ROOT / "experiments" / "pinta-eval" / name
    out_dir.mkdir(parents=True, exist_ok=True)

    records = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    boxed, probes = [], []
    for r in records:
        img = EVAL_DIR / r["image"]
        payload = detect(str(img), {"survey_id": "PINTA-EVAL", "frame_id": r["target_id"]}, settings=eval_settings)
        dets = payload.get("detections") or []
        gt = r.get("box_xyxy") if r.get("eval_class") == "wreck" else None
        row = {"target_id": r["target_id"], "classification1": r["classification1"],
               "inpainted_px": r.get("inpainted_px"), "warnings": payload.get("warnings") or []}
        if gt:
            row.update(box_xyxy=gt, **score_target(gt, dets, SETTINGS))
            boxed.append(row)
        else:
            shipped = [d for d in dets if d["calibrated_confidence"] >= floor_for(d, SETTINGS)]
            row.update(reason=r.get("eval_class_reason"),
                       shipped_reports=[{"class": detector_class(d), "conf": round(d["calibrated_confidence"], 3),
                                         "bbox": d["bbox"]} for d in shipped])
            probes.append(row)
        if not args.no_images:
            draw(img, gt or r.get("box_candidate_xyxy"), dets, SETTINGS, out_dir / f'{r["target_id"]}.jpg')

    n = len(boxed)
    summary = {
        point: {k: sum(b[point][k] for b in boxed) for k in ("found_any_class", "found_wreck_class", "centre_hit")}
        for point in ("shipped", "any")
    }
    result = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "weights": str(weights),
        "iou_found": IOU_FOUND,
        "floors": {"artificial": SETTINGS.review_floor_artificial, "net": SETTINGS.review_floor_net,
                   "natural": SETTINGS.review_floor_natural},
        "n_wrecks": n,
        "summary": summary,
        "probe_frames": len(probes),
        "probe_frames_with_false_alarm": sum(1 for p in probes if p["shipped_reports"]),
        "wrecks": boxed,
        "probes": probes,
        "caveats": "n=9, one contractor/season, marker pixels inpainted; eval only, never train",
    }
    (out_dir / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"\n  PINTA-EVAL  {n} wrecks, {len(probes)} probe frames   weights {name}")
    print(f"  {'target':<14}{'shipped: iou/class/conf':<34}any: iou/class/conf")
    for b in boxed:
        s, a = b["shipped"], b["any"]
        print(f'  {b["target_id"]:<14}{s["best_iou"]:.2f} {str(s["best_class"]):<10} {s["best_conf"] or 0:.2f}'
              f'{"":<14}{a["best_iou"]:.2f} {str(a["best_class"]):<10} {a["best_conf"] or 0:.2f}')
    for point in ("shipped", "any"):
        s = summary[point]
        print(f"  {point:<8} found(any class) {s['found_any_class']}/{n}   "
              f"found(wreck) {s['found_wreck_class']}/{n}   centre hit {s['centre_hit']}/{n}")
    print(f"  probe frames with a shipped report (false alarm): "
          f"{result['probe_frames_with_false_alarm']}/{len(probes)}")
    print(f"\n  written: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
