"""Measure global vs per-class calibration, and what it does to the review queue.

    python ai/scripts/evaluate_calibration.py --dump            # run the detector once
    python ai/scripts/evaluate_calibration.py                   # analyse the cached dump

Writes ai/experiments/calib-perclass/calibration_metrics.json. RESULTS.md beside
it is the written record of what these numbers mean.

Why a separate script from fit_calibration.py
---------------------------------------------
fit_calibration.py FITS, on validation, and writes the file the app reads.
This one JUDGES, on test, and also answers the question a calibrator change
raises that ECE does not: which detections does a reviewer now see? A
calibrated floor (review_floor_artificial = 0.20) sits on top of the
calibrated score, so moving the calibration can move recall and false alarms
without anyone touching a threshold. That has to be measured, not assumed.

The dump is detector output at conf 0.01 with the SERVED NMS settings
(Settings.iou_threshold, max_detections), each box labelled 1/0 by the same
greedy class-aware IoU >= 0.5 matching the fitter uses. Greedy matching is in
score order, so a box's label does not depend on how many weaker boxes were
also kept -- one dump answers every threshold.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))
sys.path.insert(0, str(AI_ROOT / "scripts"))

import fit_calibration as fc  # noqa: E402

OUT_DIR = AI_ROOT / "experiments" / "calib-perclass"
DUMP_CONF = 0.01


# ---------------------------------------------------------------------------
# 1. the dump
# ---------------------------------------------------------------------------

def dump(weights: Path, data_yaml: Path, split: str, device: str) -> Path:
    import yaml
    from ultralytics import YOLO

    from ghostnet.config import Settings

    settings = Settings(weights_path=weights)
    cfg = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    root = Path(cfg.get("path", data_yaml.parent))
    images = root / split / "images"
    labels_dir = root / split / "labels"
    files = sorted(p for p in images.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
    model = YOLO(str(weights))
    names = [model.names[i] for i in range(len(model.names))]

    frame, cls, score, label, area = [], [], [], [], []
    gt_frame, gt_cls = [], []
    empty = np.zeros(len(files), dtype=bool)
    for i in range(0, len(files), 16):
        chunk = files[i:i + 16]
        results = model.predict(source=[str(p) for p in chunk], imgsz=settings.imgsz,
                                conf=DUMP_CONF, iou=settings.iou_threshold,
                                max_det=settings.max_detections, device=device,
                                quantize=settings.quantize() if device != "cpu" else 32,
                                verbose=False)
        for j, (path, res) in enumerate(zip(chunk, results)):
            fi = i + j
            h, w = res.orig_shape
            gts = fc.load_gt(labels_dir / (path.stem + ".txt"), w, h)
            empty[fi] = not gts
            for g in gts:
                gt_frame.append(fi)
                gt_cls.append(g[0])
            preds = []
            for box in getattr(res, "boxes", []) or []:
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
                preds.append((float(box.conf[0]), int(box.cls[0]), (x1, y1, x2, y2)))
            preds.sort(key=lambda p: -p[0])
            for p, lab in zip(preds, fc.match(preds, gts, 0.5)):
                frame.append(fi)
                cls.append(p[1])
                score.append(p[0])
                label.append(lab)
                x1, y1, x2, y2 = p[2]
                area.append((x2 - x1) * (y2 - y1))
        print(f"  {split}: {min(i + 16, len(files))}/{len(files)} images, {len(score)} boxes", end="\r")
    print()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"dump_{split}.npz"
    np.savez_compressed(
        out, frame=np.array(frame), cls=np.array(cls), score=np.array(score),
        label=np.array(label), area=np.array(area), gt_frame=np.array(gt_frame),
        gt_cls=np.array(gt_cls), empty=empty, names=np.array(names),
        n_frames=len(files), nms_iou=settings.iou_threshold,
    )
    return out


# ---------------------------------------------------------------------------
# 2. calibration maps
# ---------------------------------------------------------------------------

def logit(s: np.ndarray) -> np.ndarray:
    p = np.clip(s, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def sig(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def nll(p: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def apply(cal: dict, s: np.ndarray, c: np.ndarray, names: list[str]) -> np.ndarray:
    """Calibrate an array of raw scores with a calibrator JSON blob, by class."""
    from ghostnet.decision import apply_map, calibrator_for

    out = np.empty_like(s, dtype=float)
    for k, name in enumerate(names):
        m = c == k
        if m.any():
            params = calibrator_for(cal, name)
            out[m] = np.array([apply_map(params, float(v)) for v in s[m]])
    return out


def reliability_table(p: np.ndarray, y: np.ndarray, bins: int = 10) -> list[dict]:
    edges = np.linspace(0, 1, bins + 1)
    rows = []
    for i in range(bins):
        m = (p > edges[i]) & (p <= edges[i + 1])
        if m.sum():
            rows.append({"bin": f"{edges[i]:.1f}-{edges[i+1]:.1f}", "n": int(m.sum()),
                         "predicted": round(float(p[m].mean()), 3),
                         "actual": round(float(y[m].mean()), 3)})
    return rows


# ---------------------------------------------------------------------------
# 3. the review queue
# ---------------------------------------------------------------------------

def band(conf: float, low: float, medium: float) -> str:
    return "low" if conf >= low else "medium" if conf >= medium else "high"


def priority(contract_class: str, uncertainty: str) -> str:
    """Mirror of app/backend detection_service._priority_for for a band.

    Re-stated rather than imported because the backend module pulls in its ORM
    and settings on import; the branch table is six lines and the test suite
    for the backend pins the original.
    """
    if contract_class == "ghost_net":
        return {"low": "CRITICAL", "medium": "HIGH"}.get(uncertainty, "MEDIUM")
    return {"low": "HIGH", "medium": "MEDIUM", "high": "LOW"}[uncertainty]


def queue(d: dict, cal: dict, names: list[str], raw_gate: float, raw_gate_net: float,
          floor: float, floor_net: float, low: float, medium: float) -> dict:
    """What the policy reports, per class, for one calibrator and one set of gates."""
    s, c, y, f = d["score"], d["cls"], d["label"], d["frame"]
    p = apply(cal, s, c, names)
    is_net = np.array([names[k] == "ghost_net" for k in c], dtype=bool)
    keep = np.where(is_net, (s >= raw_gate_net) & (p >= floor_net), (s >= raw_gate) & (p >= floor))
    out: dict = {"per_class": {}}
    for k, name in enumerate(names):
        n_gt = int((d["gt_cls"] == k).sum())
        m = keep & (c == k)
        out["per_class"][name] = {
            "gt": n_gt,
            "reported": int(m.sum()),
            "true_positives": int(y[m].sum()),
            "recall": round(float(y[m].sum() / n_gt), 4) if n_gt else None,
            "precision": round(float(y[m].mean()), 4) if m.any() else None,
        }
    empty_frames = np.where(d["empty"])[0]
    fa = np.isin(empty_frames, f[keep & ~is_net])
    out["false_alarm_rate_empty_frames"] = round(float(fa.mean()), 4)
    out["n_empty_frames"] = int(len(empty_frames))
    out["reported_total"] = int(keep.sum())

    pri = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    bands = {"low": 0, "medium": 0, "high": 0}
    for k_i, p_i in zip(c[keep], p[keep]):
        b = band(float(p_i), low, medium)
        bands[b] += 1
        pri[priority("ghost_net" if names[k_i] == "ghost_net" else "debris", b)] += 1
    out["bands"] = bands
    out["priority"] = pri
    # Precision inside each band is the only honest check that 'low'
    # uncertainty means what it says.
    bp, by_class = {}, {}
    bands_kept = np.array([band(float(v), low, medium) for v in p[keep]])
    for b_name in ("low", "medium", "high"):
        sel = bands_kept == b_name
        bp[b_name] = round(float(y[keep][sel].mean()), 4) if sel.any() else None
        for k, name in enumerate(names):
            selk = sel & (c[keep] == k)
            if selk.any():
                by_class.setdefault(name, {})[b_name] = {
                    "n": int(selk.sum()), "precision": round(float(y[keep][selk].mean()), 4)}
    out["precision_by_band"] = bp
    out["band_by_class"] = by_class
    out["band_fraction"] = {b: round(v / max(1, int(keep.sum())), 4) for b, v in bands.items()}
    return out


def derive_edges(p: np.ndarray, y: np.ndarray, low_prec: float, med_prec: float,
                 min_n: int = 20) -> dict:
    """Band edges from the calibrated distribution of SERVED val detections.

    Rule: an edge is the lowest calibrated score t such that every detection
    at or above t, taken together, is correct at least the target fraction of
    the time -- and stays so for every higher t with at least `min_n`
    detections above it (so a lucky handful at the top cannot set the edge).
    """
    order = np.argsort(-p)
    ps, ys = p[order], y[order]
    cum_prec = np.cumsum(ys) / np.arange(1, len(ys) + 1)

    def edge(target: float) -> float | None:
        ok = cum_prec >= target
        ok[:min_n - 1] = True          # too few above to judge; do not let them veto
        # lowest t such that cum_prec >= target for all prefixes from min_n up to t
        bad = np.where(~ok)[0]
        last = (bad[0] - 1) if len(bad) else len(ps) - 1
        if last < min_n - 1:
            return None
        return float(ps[last])

    return {"low": edge(low_prec), "medium": edge(med_prec)}


# ---------------------------------------------------------------------------

def load(split: str) -> dict:
    z = np.load(OUT_DIR / f"dump_{split}.npz")
    return {k: z[k] for k in z.files}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--weights", default=str(AI_ROOT / "models" / "trained" / "ghostnet.pt"))
    ap.add_argument("--data", default=str(fc.DATA_YAML))
    ap.add_argument("--device", default="0")
    ap.add_argument("--before", default=str(OUT_DIR / "temperature_before.json"),
                    help="the calibrator being replaced (git show 8ce8d9d:ai/models/calibrator/"
                         "temperature.json)")
    ap.add_argument("--after", default=str(AI_ROOT / "models" / "calibrator" / "temperature.json"))
    args = ap.parse_args()

    if args.dump:
        for split in ("val", "test"):
            print("wrote", dump(Path(args.weights), Path(args.data), split, args.device))
        return 0

    from ghostnet.config import Settings
    st = Settings()
    val, test = load("val"), load("test")
    names = [str(n) for n in val["names"]]
    before = json.loads(Path(args.before).read_text())
    after = json.loads(Path(args.after).read_text())
    min_conf = float(after.get("conf_threshold", 0.05))

    report: dict = {"names": names, "fit_population": f"raw >= {min_conf}",
                    "nms_iou": float(val["nms_iou"]), "before_file": before,
                    "after_file": {k: v for k, v in after.items() if k != "candidates"}}

    # --- calibration quality on TEST, and on val for reference --------------
    # The alternatives are fitted here from the val dump with the fitter's own
    # build_calibrator, so they differ from the shipped file only in method.
    mv0 = val["score"] >= min_conf
    sv, cv, yv = val["score"][mv0], val["cls"][mv0], val["label"][mv0].astype(float)
    platt = fc.build_calibrator(sv, cv, yv, names, "platt", int(after.get("min_positives", 30)))
    variants = {
        "before: global T 2.72 (shipped, NMS 0.7)": before,
        "global T refit, all classes pooled": {"temperature": fc.fit_temperature(sv, yv)},
        "after: per-class temperature": after,
        "alternative: per-class Platt": platt,
    }
    report["platt_candidate"] = platt
    population = {
        "fit": lambda d: d["score"] >= min_conf,
        # What a reviewer can actually be shown: the raw gates of the policy.
        "served": lambda d: np.where(np.array([names[k] == "ghost_net" for k in d["cls"]], dtype=bool),
                                     d["score"] >= st.raw_conf_threshold_net,
                                     d["score"] >= st.raw_conf_threshold),
    }
    quality = {}
    for split_name, d, pop in (("val", val, "fit"), ("test", test, "fit"),
                               ("val_served", val, "served"), ("test_served", test, "served")):
        m = population[pop](d)
        s, c, y = d["score"][m], d["cls"][m], d["label"][m].astype(float)
        rows = {}
        for vname, cal in variants.items():
            p = apply(cal, s, c, names)
            per = {}
            for k, name in enumerate(names):
                mk = c == k
                if mk.sum() == 0:
                    continue
                per[name] = {"n": int(mk.sum()), "positives": int(y[mk].sum()),
                             "ece": round(fc.ece(p[mk], y[mk]), 4), "nll": round(nll(p[mk], y[mk]), 4),
                             "max": round(float(p[mk].max()), 3),
                             "reliability": reliability_table(p[mk], y[mk])}
            rows[vname] = {"pooled_ece": round(fc.ece(p, y), 4), "pooled_nll": round(nll(p, y), 4),
                           "max": round(float(p.max()), 3), "per_class": per}
        raw = {}
        for k, name in enumerate(names):
            mk = c == k
            if mk.sum():
                raw[name] = {"ece": round(fc.ece(s[mk], y[mk]), 4), "nll": round(nll(s[mk], y[mk]), 4)}
        rows["raw"] = {"pooled_ece": round(fc.ece(s, y), 4), "pooled_nll": round(nll(s, y), 4), "per_class": raw}
        quality[split_name] = rows
    report["quality"] = quality

    # --- band edges, derived on VAL served detections ------------------------
    def served(d):
        is_net = np.array([names[k] == "ghost_net" for k in d["cls"]], dtype=bool)
        return np.where(is_net, d["score"] >= st.raw_conf_threshold_net, d["score"] >= st.raw_conf_threshold)

    mv = served(val) & np.array([names[k] != "ghost_net" for k in val["cls"]], dtype=bool)
    pv = apply(after, val["score"][mv], val["cls"][mv], names)
    edges = derive_edges(pv, val["label"][mv].astype(float), 0.80, 0.50)
    report["derived_edges_val"] = edges
    pb = apply(before, val["score"][mv], val["cls"][mv], names)
    report["derived_edges_val_before_calibrator"] = derive_edges(pb, val["label"][mv].astype(float), 0.80, 0.50)

    # --- the queue: before vs after ------------------------------------------
    # "before" is pinned to the floors and edges that shipped with the old
    # calibrator (8ce8d9d), so changing config.py cannot quietly change the
    # baseline this compares against.
    shipped = dict(raw_gate=0.10, raw_gate_net=0.03, floor=0.20, floor_net=0.10, low=0.75, medium=0.45)
    gates = dict(raw_gate=st.raw_conf_threshold, raw_gate_net=st.raw_conf_threshold_net,
                 floor=st.review_floor_artificial, floor_net=st.review_floor_net)
    report["queue"] = {}
    for split_name, d in (("val", val), ("test", test)):
        report["queue"][split_name] = {
            "before": queue(d, before, names, **shipped),
            "after, shipped floors and edges": queue(d, after, names, **shipped),
            "after": queue(d, after, names, **gates, low=st.uncertainty_low_edge,
                           medium=st.uncertainty_medium_edge),
            # The rejected alternative: edges read off val's precision curve.
            "after, val-precision edges": queue(d, after, names, **gates, low=edges["low"],
                                                medium=edges["medium"]),
        }
    # Floor sweep: what calibrated floor would hold the shipped recall exactly.
    sweep = []
    for fl in [0.0, 0.05, 0.10, 0.12, 0.15, 0.20, 0.25, 0.30]:
        q = queue(test, after, names, raw_gate=st.raw_conf_threshold, raw_gate_net=st.raw_conf_threshold_net,
                  floor=fl, floor_net=st.review_floor_net, low=st.uncertainty_low_edge,
                  medium=st.uncertainty_medium_edge)
        sweep.append({"floor": fl, "fa": q["false_alarm_rate_empty_frames"],
                      "recall": {n: v["recall"] for n, v in q["per_class"].items()},
                      "reported": q["reported_total"]})
    report["floor_sweep_test_after"] = sweep
    report["settings"] = {**gates, "uncertainty_low_edge": st.uncertainty_low_edge,
                          "uncertainty_medium_edge": st.uncertainty_medium_edge}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "calibration_metrics.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("derived_edges_val", "derived_edges_val_before_calibrator")}, indent=1))
    for split_name in quality:
        print("\n==", split_name)
        for vname, r in quality[split_name].items():
            print(f"  {vname:42s} ECE {r['pooled_ece']:.4f} NLL {r['pooled_nll']:.4f}  " + "  ".join(
                f"{n}:{v['ece']:.3f}" for n, v in r["per_class"].items()))
        for qn, q in report["queue"].get(split_name, {}).items():
            print(f"  {qn:16s} FA {q['false_alarm_rate_empty_frames']:.4f} rep {q['reported_total']} "
                  + " ".join(f"{n}:{v['recall']}" for n, v in q["per_class"].items())
                  + f" bands {q['bands']} pri {q['priority']} prec {q['precision_by_band']}")
    print("\nfloor sweep (test, after):")
    for r in sweep:
        print("  ", r)
    print("\nwrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
