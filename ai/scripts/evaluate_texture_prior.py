"""Does a hand-made mesh-texture score separate real ghost nets from everything else?

    python ai/scripts/evaluate_texture_prior.py
    python ai/scripts/evaluate_texture_prior.py --sheet     # also write contact sheets

Writes ai/experiments/texture-prior/{results.json,scores.csv,sheet_*.png}

The idea being tested
---------------------
A net is a mesh, so a patch of net should carry a regular crossing texture:
two dominant orientations at one spatial period. If a fixed filter can see
that, it could run beside the detector as a low-confidence "possible net"
flag. A fixed filter never trains, so it cannot overfit 51 frames the way
the detector did on GHOSTNET-SYNTH.

This script measures whether that is true before anything is built on it.

Why the negatives are chosen the way they are
---------------------------------------------
All 73 real net frames come from ONE source (GHOSTNET-HAND). A score that only
beat negatives from other datasets could be separating the sensor, not the net.
So negatives come in three groups, reported separately:

* ``same_frame``  -- windows from the net frames themselves, clear of every box.
                    Same sonar, same survey, same noise. The control that matters.
* ``textured``    -- the highest-contrast quarter of random empty-seabed
                    windows from other sources (ripples, scars, rock): the
                    likely false alarms.
* ``other_class`` -- wreck, debris and pot boxes.

Why fixed 64 px windows at native resolution
--------------------------------------------
Net boxes range from about 60 to 300 px. Scoring whole boxes would let patch
size leak into every spectral feature, and resizing would move the mesh
period. One 64 px window per sample keeps both fixed.

Honesty rule
------------
Every score's direction ("higher means net") is chosen on the TRAIN split
only. Val and test (83 real boxes) are read once, as a holdout. Tuning against
them would make any AUROC here meaningless.

Controls
--------
``ctl_*`` scores are deliberately texture-blind: brightness, contrast, edge
density. If a control does as well as a texture score, the texture score is
finding something other than mesh.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

import cv2
import numpy as np

AI_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = Path("E:/New folder/ai/data/processed")
OUT = AI_ROOT / "experiments" / "texture-prior"

NET, OTHER_CLASSES = 4, (0, 2, 3)
WIN = 64
#: Periods, in pixels, a resolvable mesh could have in a 64 px window.
PERIOD_MIN, PERIOD_MAX = 3.0, 16.0
#: Sources whose empty frames supply "textured seabed" negatives. Real sonar
#: only; GHOSTNET-SYNTH is excluded on principle.
SEABED_SOURCES = ("CHINA-OFFSHORE", "AI4SHIPWRECKS", "SUBPIPE", "SCTD")
SEED = 0


# --------------------------------------------------------------------- scores

def _hann2d(n: int) -> np.ndarray:
    w = np.hanning(n)
    return np.outer(w, w)


_HANN = _hann2d(WIN)
_fy, _fx = np.meshgrid(np.fft.fftshift(np.fft.fftfreq(WIN)),
                       np.fft.fftshift(np.fft.fftfreq(WIN)), indexing="ij")
_RADIUS = np.hypot(_fx, _fy)
_BAND = (_RADIUS >= 1 / PERIOD_MAX) & (_RADIUS <= 1 / PERIOD_MIN)
_NONDC = _RADIUS > 1 / WIN


def _normalise(p: np.ndarray) -> np.ndarray:
    """Zero mean, unit variance: texture scores must not see brightness."""
    p = p.astype(np.float32)
    return (p - p.mean()) / (p.std() + 1e-6)


def _spectrum(p: np.ndarray) -> np.ndarray:
    return np.abs(np.fft.fftshift(np.fft.fft2(_normalise(p) * _HANN))) ** 2


def fft_peak(p: np.ndarray) -> float:
    """Strongest single frequency in the mesh band, over the band's median."""
    band = _spectrum(p)[_BAND]
    return float(np.log(band.max() / (np.median(band) + 1e-9)))


def fft_band(p: np.ndarray) -> float:
    """Share of non-DC power that sits at mesh-like periods."""
    s = _spectrum(p)
    return float(s[_BAND].sum() / (s[_NONDC].sum() + 1e-9))


_THETAS = np.deg2rad(np.arange(0, 180, 22.5))
_LAMBDAS = (4.0, 6.0, 9.0, 13.0)
_GABOR = {
    lam: [cv2.getGaborKernel((31, 31), sigma=0.56 * lam, theta=t, lambd=lam,
                             gamma=0.5, psi=0, ktype=cv2.CV_32F)
          for t in _THETAS]
    for lam in _LAMBDAS
}


def _orientation_energy(p: np.ndarray) -> dict[float, np.ndarray]:
    x = _normalise(p)
    out = {}
    for lam, bank in _GABOR.items():
        e = []
        for k in bank:
            k = k - k.mean()
            r = cv2.filter2D(x, cv2.CV_32F, k)[8:-8, 8:-8]
            e.append(float((r ** 2).mean()))
        out[lam] = np.array(e)
    return out


def gabor_aniso(p: np.ndarray) -> float:
    """One dominant orientation: ripples and scars score high here."""
    return float(max(e.max() / (e.mean() + 1e-9)
                     for e in _orientation_energy(p).values()))


def gabor_cross(p: np.ndarray) -> float:
    """Two strong orientations at least 45 deg apart, at the same period.

    The mesh hypothesis in one number: a net should light up two crossing
    directions, a ripple field only one.
    """
    best = 0.0
    n = len(_THETAS)
    for e in _orientation_energy(p).values():
        i = int(e.argmax())
        far = [j for j in range(n) if min(abs(j - i), n - abs(j - i)) >= 2]
        second = max(e[j] for j in far)
        best = max(best, float(second / (e.mean() + 1e-9)))
    return best


def ctl_mean(p: np.ndarray) -> float:
    return float(p.mean())


def ctl_std(p: np.ndarray) -> float:
    return float(p.std())


def ctl_edges(p: np.ndarray) -> float:
    gx = cv2.Sobel(p.astype(np.float32), cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(p.astype(np.float32), cv2.CV_32F, 0, 1)
    return float(np.hypot(gx, gy).mean())


def user_score(p: np.ndarray) -> float:
    """Your own mesh-ness score. Return a float, higher = more net-like.

    `p` is a 64x64 uint8 grayscale window at native sonar resolution.
    Leave it raising NotImplementedError and it is simply skipped.
    """
    raise NotImplementedError


SCORES = {f.__name__: f for f in (fft_peak, fft_band, gabor_aniso, gabor_cross,
                                  ctl_mean, ctl_std, ctl_edges, user_score)}


# -------------------------------------------------------------------- samples

def _read_boxes(label: Path, w: int, h: int) -> list[tuple[int, int, int, int, int]]:
    boxes = []
    for line in label.read_text().splitlines():
        f = line.split()
        if len(f) < 5:
            continue
        c, cx, cy, bw, bh = int(f[0]), *map(float, f[1:5])
        boxes.append((c, int((cx - bw / 2) * w), int((cy - bh / 2) * h),
                      int((cx + bw / 2) * w), int((cy + bh / 2) * h)))
    return boxes


def _image_for(split_dir: Path, stem: str) -> Path | None:
    for ext in (".png", ".jpg", ".jpeg"):
        p = split_dir / "images" / f"{stem}{ext}"
        if p.exists():
            return p
    return None


def _window_at(img: np.ndarray, cx: int, cy: int) -> np.ndarray | None:
    h, w = img.shape
    if w < WIN or h < WIN:
        return None
    x0 = min(max(cx - WIN // 2, 0), w - WIN)
    y0 = min(max(cy - WIN // 2, 0), h - WIN)
    return img[y0:y0 + WIN, x0:x0 + WIN]


def _clear_of(x0, y0, boxes) -> bool:
    return all(x0 + WIN <= b[1] or x0 >= b[3] or y0 + WIN <= b[2] or y0 >= b[4]
               for b in boxes)


def collect(data: Path, splits: tuple[str, ...], rng: random.Random,
            n_textured: int, n_other: int) -> list[dict]:
    samples = []
    labels = sorted(p for s in splits for p in (data / s / "labels").glob("*.txt"))

    # positives + same-frame negatives
    for lf in labels:
        if not lf.name.startswith("GHOSTNET-HAND"):
            continue
        split_dir = lf.parent.parent
        img = cv2.imread(str(_image_for(split_dir, lf.stem)), cv2.IMREAD_GRAYSCALE)
        h, w = img.shape
        boxes = _read_boxes(lf, w, h)
        for b in boxes:
            if b[0] == NET:
                win = _window_at(img, (b[1] + b[3]) // 2, (b[2] + b[4]) // 2)
                if win is not None:
                    samples.append(dict(y=1, group="net", src=lf.stem, win=win))
        if w >= WIN and h >= WIN:
            for _ in range(2):
                for _try in range(200):
                    x0, y0 = rng.randint(0, w - WIN), rng.randint(0, h - WIN)
                    if _clear_of(x0, y0, boxes):
                        samples.append(dict(y=0, group="same_frame", src=lf.stem,
                                            win=img[y0:y0 + WIN, x0:x0 + WIN]))
                        break

    # textured seabed: most-textured quarter of random empty-frame windows
    empty = [lf for lf in labels if lf.name.split("__")[0] in SEABED_SOURCES
             and not lf.read_text().strip()]
    cands = []
    for lf in rng.sample(empty, min(len(empty), n_textured * 4)):
        img = cv2.imread(str(_image_for(lf.parent.parent, lf.stem)), cv2.IMREAD_GRAYSCALE)
        if img is None or min(img.shape) < WIN:
            continue
        h, w = img.shape
        win = img[rng.randint(0, h - WIN):, rng.randint(0, w - WIN):][:WIN, :WIN]
        # Ranked by contrast, not by any texture score under test, so the
        # selection cannot rig one score's result on this group.
        cands.append((float(win.std()), lf.stem, win))
    cands.sort(key=lambda c: -c[0])
    for _, stem, win in cands[:n_textured]:
        samples.append(dict(y=0, group="textured", src=stem, win=win))

    # other classes, balanced
    per_class = {c: [] for c in OTHER_CLASSES}
    for lf in labels:
        if "SYNTH" in lf.name or not lf.read_text().strip():
            continue
        for line in lf.read_text().splitlines():
            f = line.split()
            if f and int(f[0]) in OTHER_CLASSES:
                per_class[int(f[0])].append(lf)
                break
    for c, files in per_class.items():
        for lf in rng.sample(files, min(len(files), n_other // len(OTHER_CLASSES))):
            img = cv2.imread(str(_image_for(lf.parent.parent, lf.stem)), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            h, w = img.shape
            b = [b for b in _read_boxes(lf, w, h) if b[0] == c][0]
            win = _window_at(img, (b[1] + b[3]) // 2, (b[2] + b[4]) // 2)
            if win is not None:
                samples.append(dict(y=0, group="other_class", src=lf.stem, win=win))
    return samples


# ------------------------------------------------------------------- analysis

def auroc(pos: np.ndarray, neg: np.ndarray) -> float:
    """Mann-Whitney: P(score of a random net > score of a random non-net)."""
    allv = np.concatenate([pos, neg])
    ranks = allv.argsort().argsort().astype(float) + 1
    # average ranks for ties
    for v in np.unique(allv):
        m = allv == v
        if m.sum() > 1:
            ranks[m] = ranks[m].mean()
    r_pos = ranks[: len(pos)].sum()
    return float((r_pos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def bootstrap_ci(pos, neg, rng: np.random.Generator, n=1000) -> tuple[float, float]:
    vals = [auroc(rng.choice(pos, len(pos)), rng.choice(neg, len(neg))) for _ in range(n)]
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def score_all(samples: list[dict], names: list[str]) -> None:
    for s in samples:
        s["scores"] = {n: SCORES[n](s["win"]) for n in names}


def table(samples, names, sign) -> dict:
    groups = ["all", "same_frame", "textured", "other_class"]
    pos = [s for s in samples if s["y"] == 1]
    out = {}
    for n in names:
        p = np.array([s["scores"][n] for s in pos]) * sign[n]
        row = {}
        for g in groups:
            neg = [s for s in samples if s["y"] == 0 and (g == "all" or s["group"] == g)]
            q = np.array([s["scores"][n] for s in neg]) * sign[n]
            row[g] = auroc(p, q) if len(q) else None
        out[n] = row
    return out


def contact_sheet(samples, group, path, k=40):
    picks = [s["win"] for s in samples if s["group"] == group][:k]
    if not picks:
        return
    cols = 10
    rows = (len(picks) + cols - 1) // cols
    sheet = np.full((rows * (WIN + 4), cols * (WIN + 4)), 255, np.uint8)
    for i, w in enumerate(picks):
        r, c = divmod(i, cols)
        sheet[r * (WIN + 4): r * (WIN + 4) + WIN, c * (WIN + 4): c * (WIN + 4) + WIN] = w
    cv2.imwrite(str(path), cv2.resize(sheet, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--sheet", action="store_true", help="write contact sheets")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    rng = random.Random(SEED)
    dev = collect(a.data, ("train",), rng, n_textured=100, n_other=99)
    hold = collect(a.data, ("val", "test"), rng, n_textured=80, n_other=81)

    names = []
    for n, f in SCORES.items():
        try:
            f(dev[0]["win"])
            names.append(n)
        except NotImplementedError:
            pass
    score_all(dev, names)
    score_all(hold, names)

    # direction fixed on dev only
    raw = table(dev, names, {n: 1 for n in names})
    sign = {n: 1 if raw[n]["all"] >= 0.5 else -1 for n in names}
    dev_t, hold_t = table(dev, names, sign), table(hold, names, sign)

    brng = np.random.default_rng(SEED)
    ci = {}
    for n in names:
        p = np.array([s["scores"][n] for s in hold if s["y"] == 1]) * sign[n]
        q = np.array([s["scores"][n] for s in hold if s["y"] == 0]) * sign[n]
        ci[n] = bootstrap_ci(p, q, brng)

    # Every texture score, combined: logistic regression fit on dev only.
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    tex = [n for n in names if not n.startswith("ctl_")]
    X = lambda ss: np.array([[s["scores"][n] for n in tex] for s in ss])
    y = lambda ss: np.array([s["y"] for s in ss])
    scaler = StandardScaler().fit(X(dev))
    clf = LogisticRegression(max_iter=1000).fit(scaler.transform(X(dev)), y(dev))
    for ss in (dev, hold):
        for s, v in zip(ss, clf.predict_proba(scaler.transform(X(ss)))[:, 1]):
            s["scores"]["combined"] = float(v)
    sign["combined"] = 1
    dev_t["combined"] = table(dev, ["combined"], sign)["combined"]
    hold_t["combined"] = table(hold, ["combined"], sign)["combined"]
    p = np.array([s["scores"]["combined"] for s in hold if s["y"] == 1])
    q = np.array([s["scores"]["combined"] for s in hold if s["y"] == 0])
    ci["combined"] = bootstrap_ci(p, q, brng)

    counts = {k: {g: sum(1 for s in ss if s["group"] == g)
                  for g in ("net", "same_frame", "textured", "other_class")}
              for k, ss in (("dev", dev), ("holdout", hold))}
    result = dict(counts=counts, direction=sign, dev=dev_t, holdout=hold_t,
                  holdout_ci95=ci, combined_features=tex)
    (OUT / "results.json").write_text(json.dumps(result, indent=2))

    with open(OUT / "scores.csv", "w", newline="") as fh:
        wr = csv.writer(fh)
        cols = names + ["combined"]
        wr.writerow(["split", "y", "group", "src"] + cols)
        for k, ss in (("dev", dev), ("holdout", hold)):
            for s in ss:
                wr.writerow([k, s["y"], s["group"], s["src"]] + [round(s["scores"][n], 5) for n in cols])

    if a.sheet:
        for g in ("net", "same_frame", "textured", "other_class"):
            contact_sheet(dev, g, OUT / f"sheet_{g}.png")

    print("counts", json.dumps(counts))
    hdr = f"{'score':<12}{'dir':>4}  {'dev all':>8}  {'HOLD all':>8}  {'95% CI':>13}  {'same_fr':>7}  {'textrd':>7}  {'other':>7}"
    print(hdr)
    for n in list(names) + ["combined"]:
        h = hold_t[n]
        print(f"{n:<12}{'+' if sign[n] > 0 else '-':>4}  {dev_t[n]['all']:8.3f}  {h['all']:8.3f}  "
              f"{ci[n][0]:6.3f}-{ci[n][1]:.3f}  {h['same_frame']:7.3f}  {h['textured']:7.3f}  {h['other_class']:7.3f}")


if __name__ == "__main__":
    main()
