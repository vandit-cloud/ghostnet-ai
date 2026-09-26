"""Top-confidence ghost_pot 'false positives' on TRAIN frames, cropped, for eyeballing.
Also prints train precision/recall at a few confidences."""
import random, sys
from pathlib import Path
import cv2, numpy as np
from ultralytics import YOLO

W = sys.argv[1]
OUTP = Path(sys.argv[2])
D = Path("E:/New folder/ai/data/processed")
files = [l.strip() for l in (D / "train_nosynth.txt").read_text().splitlines() if "GHOSTVISION" in l]
rng = random.Random(1)
files = rng.sample(files, 400)
m = YOLO(W)

def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy; u = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - i
    return i / u if u > 0 else 0

preds, ntruth = [], 0
for f in files:
    lbl = Path(f.replace("/images/", "/labels/")).with_suffix(".txt")
    truth = []
    for line in lbl.read_text().splitlines() if lbl.exists() else []:
        p = line.split()
        if p and p[0] == "3":
            x, y, w, h = map(float, p[1:5]); truth.append((x-w/2, y-h/2, x+w/2, y+h/2))
    ntruth += len(truth)
    r = m.predict(f, imgsz=640, conf=0.01, device="0", verbose=False)[0]
    for b, c, k in zip(r.boxes.xyxyn.tolist(), r.boxes.conf.tolist(), r.boxes.cls.tolist()):
        if int(k) != 3: continue
        best = max((iou(b, t) for t in truth), default=0)
        preds.append((c, best >= 0.5, best, f, b))

preds.sort(key=lambda p: -p[0])
for thr in (0.05, 0.1, 0.25):
    sel = [p for p in preds if p[0] >= thr]
    tp = sum(p[1] for p in sel)
    print(f"conf {thr}: preds {len(sel)}  TP {tp}  precision {tp/max(len(sel),1):.3f}  (truth boxes {ntruth})")
conf_tp = [p[0] for p in preds if p[1]]; conf_fp = [p[0] for p in preds if not p[1] and p[0] >= 0.05]
print(f"median conf TP {np.median(conf_tp):.3f}   median conf FP(>=0.05) {np.median(conf_fp):.3f}")
fps = [p for p in preds if not p[1] and p[2] < 0.1][:40]
tps = [p for p in preds if p[1]][:8]

def crop(f, b, col):
    im = cv2.imread(f); H, Wd = im.shape[:2]
    x1, y1, x2, y2 = int(b[0]*Wd), int(b[1]*H), int(b[2]*Wd), int(b[3]*H)
    cx, cy = (x1+x2)//2, (y1+y2)//2; s = max(64, int(1.8*max(x2-x1, y2-y1)))
    cv2.rectangle(im, (x1, y1), (x2, y2), col, 1)
    pad = cv2.copyMakeBorder(im, s, s, s, s, cv2.BORDER_CONSTANT)
    c = pad[cy:cy+2*s, cx:cx+2*s]
    return cv2.resize(c, (150, 150), interpolation=cv2.INTER_NEAREST)

cells = [crop(p[3], p[4], (0, 0, 255)) for p in fps] + [crop(p[3], p[4], (0, 255, 0)) for p in tps]
for i, (c, p) in enumerate(zip(cells, fps + tps)):
    cv2.putText(c, f"{p[0]:.2f}", (3, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)
while len(cells) % 8: cells.append(np.zeros_like(cells[0]))
cv2.imwrite(str(OUTP), np.vstack([np.hstack(cells[i:i+8]) for i in range(0, len(cells), 8)]))
print("rows 1-5 = top-40 FPs (red box, no truth pot within IoU 0.1); row 6 = top TPs (green)")
