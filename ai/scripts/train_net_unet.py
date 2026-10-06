"""Train the ghost_net U-Net (Track U). See _net_unet.py for why it exists.

    python ai/scripts/train_net_unet.py --name gvU1-unet-s0
    python ai/scripts/train_net_unet.py --name gvU1n-unet-hardneg-s0 \
        --data "E:/New folder/ai/data/net_seg_hardneg"
    python ai/scripts/train_net_unet.py --name <same> --resume

Writes ai/experiments/<name>/ only: weights/best.pt, weights/last.pt,
results.csv, provenance.json.

What is held equal to the YOLO-seg runs, and what cannot be
------------------------------------------------------------
Held equal: the dataset directories (same 51 or 153 train chips, the same
11 val and 11 test chips), 640 input, batch 4, seed, flips on (port/starboard
mirror and reversed vessel heading are both real surveys), rotation OFF
(across-track is range, so a rotated tile is not a sonar image), best
checkpoint chosen on val.

Cannot be held equal: mosaic. It is an instance-detection augmentation built
into Ultralytics' loader. The U-Net gets the closest per-pixel equivalent
instead, a random rescale (0.5-1.5, YOLO's `scale=0.5`) with a random
placement on the canvas (YOLO's `translate=0.1`), plus a brightness/contrast
jitter standing in for `hsv_v=0.4`.

Model selection
---------------
best.pt is the epoch with the highest val Dice at a 0.5 pixel threshold.
Val holds no empty chips, in net_seg and net_seg_hardneg alike, so selection
cannot reward suppressing false alarms. That is the same blind spot the YOLO
runs' val fitness had, so the comparison stays fair; the false-alarm rate is
measured afterwards on the 100 held-out empty chips.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _net_unet as U  # noqa: E402

AI_ROOT = Path(__file__).resolve().parent.parent
EXPERIMENTS = AI_ROOT / "experiments"
DATA = Path("E:/New folder/ai/data/net_seg")


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=AI_ROOT.parent,
                              capture_output=True, text=True, timeout=10).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


class ChipSet:
    """Chips held in memory at native size. 153 chips of ~350 px is ~20 MB."""

    def __init__(self, data_dir: Path, split: str, augment: bool, rng: random.Random):
        self.items = []
        for img_p, lbl_p in U.list_split(data_dir, split):
            g = U.read_gray(img_p)
            m = U.polygons_to_mask(U.read_polygons(lbl_p), *g.shape)
            self.items.append((img_p.name, g, m))
        self.augment = augment
        self.rng = rng

    def __len__(self) -> int:
        return len(self.items)

    def sample(self, i: int) -> tuple[np.ndarray, np.ndarray]:
        _, g, m = self.items[i]
        if not self.augment:
            gi, _ = U.letterbox(g)
            mi, _ = U.letterbox(m, interp=cv2.INTER_NEAREST, pad=0)
            return gi, mi
        r = self.rng
        if r.random() < 0.5:
            g, m = g[:, ::-1], m[:, ::-1]
        if r.random() < 0.5:
            g, m = g[::-1], m[::-1]
        h, w = g.shape
        s = U.IMGSZ / max(h, w) * r.uniform(0.5, 1.5)
        nh, nw = max(1, round(h * s)), max(1, round(w * s))
        g = cv2.resize(np.ascontiguousarray(g), (nw, nh), interpolation=cv2.INTER_LINEAR)
        m = cv2.resize(np.ascontiguousarray(m), (nw, nh), interpolation=cv2.INTER_NEAREST)
        # brightness/contrast jitter, the grey analogue of hsv_v=0.4
        gain, bias = r.uniform(0.6, 1.4), r.uniform(-25, 25)
        g = np.clip(g.astype(np.float32) * gain + bias, 0, 255).astype(np.uint8)
        # random placement on the canvas: pads when small, crops when large
        S = U.IMGSZ
        gc = np.full((S, S), U.PAD_VALUE, np.uint8)
        mc = np.zeros((S, S), np.uint8)
        ox = r.randint(min(0, S - nw), max(0, S - nw))
        oy = r.randint(min(0, S - nh), max(0, S - nh))
        sx0, sy0 = max(0, -ox), max(0, -oy)
        dx0, dy0 = max(0, ox), max(0, oy)
        cw, ch = min(nw - sx0, S - dx0), min(nh - sy0, S - dy0)
        gc[dy0:dy0 + ch, dx0:dx0 + cw] = g[sy0:sy0 + ch, sx0:sx0 + cw]
        mc[dy0:dy0 + ch, dx0:dx0 + cw] = m[sy0:sy0 + ch, sx0:sx0 + cw]
        return gc, mc


def batches(ds: ChipSet, batch: int, shuffle: bool, rng: random.Random):
    import torch
    idx = list(range(len(ds)))
    if shuffle:
        rng.shuffle(idx)
    for k in range(0, len(idx), batch):
        pairs = [ds.sample(i) for i in idx[k:k + batch]]
        x = torch.cat([U.to_tensor(g) for g, _ in pairs])
        y = torch.from_numpy(np.stack([m for _, m in pairs]).astype(np.float32))[:, None]
        yield x, y


def val_dice(model, ds: ChipSet, device: str) -> float:
    """Pooled Dice over the whole split at threshold 0.5, at NATIVE resolution."""
    inter = total = 0
    for _, g, m in ds.items:
        pred = U.predict_prob(model, g, device) >= 0.5
        inter += int((pred & (m > 0)).sum())
        total += int(pred.sum()) + int((m > 0).sum())
    return 2 * inter / total if total else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser(description="Train the ghost_net U-Net")
    ap.add_argument("--name", required=True)
    ap.add_argument("--data", type=Path, default=DATA)
    ap.add_argument("--encoder", default="resnet34")
    ap.add_argument("--epochs", type=int, default=300)
    ap.add_argument("--batch", type=int, default=4, help="parity with YOLO-seg runs")
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--val-every", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    import torch
    import segmentation_models_pytorch as smp

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    rng = random.Random(args.seed)

    out = EXPERIMENTS / args.name
    (out / "weights").mkdir(parents=True, exist_ok=True)
    train = ChipSet(args.data, "train", augment=True, rng=rng)
    val = ChipSet(args.data, "val", augment=False, rng=rng)
    n_neg = sum(int(m.max() == 0) for _, _, m in train.items)
    print(f"  data    {args.data}")
    print(f"  train   {len(train)} chips ({n_neg} empty)   val {len(val)}")
    print(f"  model   U-Net / {args.encoder}   epochs {args.epochs}   batch {args.batch}   seed {args.seed}")

    model = U.build_model(args.encoder).to(args.device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    steps_per_epoch = math.ceil(len(train) / args.batch)
    sched = torch.optim.lr_scheduler.OneCycleLR(
        opt, max_lr=args.lr, total_steps=args.epochs * steps_per_epoch, pct_start=0.05)
    scaler = torch.amp.GradScaler("cuda", enabled=args.device.startswith("cuda"))
    # Dice over the whole batch (smp aggregates over batch and pixels), so an
    # all-empty chip contributes through BCE and the batch Dice rather than
    # making a per-image Dice of 0/0.
    dice_loss = smp.losses.DiceLoss("binary", from_logits=True)
    bce_loss = smp.losses.SoftBCEWithLogitsLoss()

    start, best = 1, -1.0
    csv_path = out / "results.csv"
    if args.resume and (out / "weights" / "last.pt").exists():
        ck = torch.load(out / "weights" / "last.pt", map_location=args.device, weights_only=False)
        model.load_state_dict(ck["model"])
        opt.load_state_dict(ck["opt"])
        sched.load_state_dict(ck["sched"])
        scaler.load_state_dict(ck["scaler"])
        rng.setstate(ck["rng"])
        start, best = ck["epoch"] + 1, ck["best"]
        print(f"  resumed at epoch {start}, best val Dice so far {best:.4f}")
    else:
        csv_path.write_text("epoch,time,train_loss,val_dice,lr\n")

    def save(path: Path, epoch: int) -> None:
        torch.save({"model": model.state_dict(), "opt": opt.state_dict(),
                    "sched": sched.state_dict(), "scaler": scaler.state_dict(),
                    "rng": rng.getstate(), "epoch": epoch, "best": best,
                    "encoder": args.encoder, "imgsz": U.IMGSZ}, path)

    t0 = time.time()
    for epoch in range(start, args.epochs + 1):
        model.train()
        losses = []
        for x, y in batches(train, args.batch, shuffle=True, rng=rng):
            x, y = x.to(args.device), y.to(args.device)
            with torch.autocast(device_type="cuda", enabled=args.device.startswith("cuda")):
                logits = model(x)
            logits = logits.float()
            loss = bce_loss(logits, y) + dice_loss(logits, y)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            sched.step()
            losses.append(loss.item())

        vd = ""
        if epoch % args.val_every == 0 or epoch == args.epochs:
            model.eval()
            d = val_dice(model, val, args.device)
            vd = f"{d:.5f}"
            if d > best:
                best = d
                save(out / "weights" / "best.pt", epoch)
            save(out / "weights" / "last.pt", epoch)
            print(f"  epoch {epoch:4d}/{args.epochs}  loss {np.mean(losses):.4f}  "
                  f"val Dice {d:.4f}  best {best:.4f}  ({time.time() - t0:.0f}s)", flush=True)
        with csv_path.open("a", newline="") as f:
            csv.writer(f).writerow([epoch, round(time.time() - t0, 1),
                                    round(float(np.mean(losses)), 5), vd,
                                    f"{sched.get_last_lr()[0]:.3e}"])

    (out / "provenance.json").write_text(json.dumps({
        "run": args.name, "task": "semantic segmentation (U-Net)", "classes": ["ghost_net"],
        "encoder": args.encoder, "encoder_weights": "imagenet", "in_channels": 1,
        "data": str(args.data), "train_chips": len(train), "train_empty_chips": n_neg,
        "seed": args.seed, "epochs": args.epochs, "batch": args.batch, "lr": args.lr,
        "imgsz": U.IMGSZ, "loss": "BCE + Dice (batch-aggregated)",
        "augment": "flip lr/ud, rescale 0.5-1.5 + random placement, gain 0.6-1.4, bias +-25; no rotation",
        "selection": "best val Dice @0.5 (val has no empty chips)",
        "best_val_dice": best, "git_commit": git_commit(), "cli": " ".join(sys.argv),
        "caveat": "test split is 11 chips -- upper bound only; review candidate, not a detection claim.",
    }, indent=2), encoding="utf-8")
    print(f"\n  done. best val Dice {best:.4f}. Score with evaluate_net_unet.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
