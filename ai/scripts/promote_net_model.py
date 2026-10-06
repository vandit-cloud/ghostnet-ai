"""Promote a trained ghost_net U-Net run to the model the app serves.

    python ai/scripts/promote_net_model.py --run gvU1n-unet-hardneg-s1
    python ai/scripts/promote_net_model.py --run <run> --force   # replace an existing one

Writes two files into ai/models/trained/ (both gitignored, and they must travel
together):

* ghostnet_net.pt   -- a SLIM checkpoint: weights, encoder name and imgsz only.
  The training checkpoint also carries optimiser, scheduler, scaler and RNG
  state, about three times the size, none of which inference reads. Holding
  only tensors and strings, it loads under torch's weights_only mode, which
  refuses to execute pickled code.
* ghostnet_net.json -- the sidecar Settings reads net_model_version from. It
  names the source run and hashes both files, so "the app serves gvU1n-s1" is
  checkable rather than asserted.

Before writing anything, the slim weights are reloaded through ghostnet.unet
(the loader the web app uses) and must reproduce the source model's output on
a fixed input exactly. A promotion that changes the model is refused.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT))

from ghostnet import unet  # noqa: E402

EXPERIMENTS = AI_ROOT / "experiments"
TRAINED = AI_ROOT / "models" / "trained"
SCORING = EXPERIMENTS / "unet-scoring"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def outputs_match(source: dict, slim_path: Path) -> bool:
    """Same logits from the source weights and from the reloaded slim file."""
    import torch

    a = unet.build_model(source["encoder"], weights=None)
    a.load_state_dict(source["model"])
    b, _ = unet.load_checkpoint(slim_path, "cpu")
    a.eval()
    x = torch.linspace(-1, 1, 640 * 640).reshape(1, 1, 640, 640)
    with torch.no_grad():
        return bool(torch.equal(a(x), b(x)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="experiment name under ai/experiments/")
    ap.add_argument("--checkpoint", default="best.pt", help="file inside <run>/weights/ (default best.pt)")
    ap.add_argument("--force", action="store_true", help="replace an existing promoted net model")
    args = ap.parse_args()

    import torch

    run_dir = EXPERIMENTS / args.run
    src = run_dir / "weights" / args.checkpoint
    dest = TRAINED / "ghostnet_net.pt"
    sidecar = dest.with_suffix(".json")

    if not src.exists():
        print(f"no checkpoint at {src}")
        return 1
    if dest.exists() and not args.force:
        print(f"{dest} already exists (model_version "
              f"{json.loads(sidecar.read_text()).get('model_version', '?') if sidecar.exists() else '?'}). "
              "Pass --force to replace it.")
        return 1

    source = unet.read_checkpoint(src)
    if source is None:
        print(f"{src} is not a U-Net checkpoint; this script promotes U-Nets only")
        return 1

    # Everything that can fail runs BEFORE either live file is touched: reading
    # the run's JSON, writing and verifying the slim weights, hashing. Only then
    # are the two files swapped in, back to back, so a failure can never leave
    # new weights beside an old sidecar -- which would stamp every payload with
    # the previous run's version while serving the new one.
    provenance = {}
    if (run_dir / "provenance.json").exists():
        provenance = json.loads((run_dir / "provenance.json").read_text(encoding="utf-8"))
    score_path = SCORING / f"{args.run}.json"
    if score_path.exists():
        json.loads(score_path.read_text(encoding="utf-8"))   # must parse; only its path is recorded

    TRAINED.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".pt.tmp")
    tmp_meta = sidecar.with_suffix(".json.tmp")
    try:
        torch.save({"model": source["model"], "encoder": source["encoder"],
                    "imgsz": int(source.get("imgsz") or unet.IMGSZ)}, tmp)
        if not outputs_match(source, tmp):
            print("refused: the slim checkpoint does not reproduce the source model's output")
            return 1
        meta = {
            "model_version": args.run,
            "kind": "unet",
            "encoder": source["encoder"],
            "imgsz": int(source.get("imgsz") or unet.IMGSZ),
            "operating_point": "pixel threshold Settings.net_unet_threshold (0.5, fixed in unet-scoring/PLAN.md)",
            "promoted_from": str(src.relative_to(AI_ROOT.parent)).replace("\\", "/"),
            "promoted_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sha256": sha256(tmp),
            "source_sha256": sha256(src),
            "epoch": source.get("epoch"),
            "best_val_dice": source.get("best"),
            "train_data": provenance.get("data"),
            "train_git_commit": provenance.get("git_commit"),
            "test_scoring": f"ai/experiments/unet-scoring/{args.run}.json" if score_path.exists() else None,
            "note": ("Written by promote_net_model.py. Must travel WITH ghostnet_net.pt -- both are "
                     "gitignored, and without this file net_model_version falls back to the file stem. "
                     "Test figures are on 11 chips from 2 sites: an upper bound for a review "
                     "candidate, never a detection claim."),
        }
        tmp_meta.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        tmp.replace(dest)
        tmp_meta.replace(sidecar)
    finally:
        for leftover in (tmp, tmp_meta):
            if leftover.exists():
                leftover.unlink()

    mb = dest.stat().st_size / 1e6
    print(f"promoted {args.run} -> {dest.relative_to(AI_ROOT.parent)} ({mb:.1f} MB, "
          f"from {src.stat().st_size / 1e6:.1f} MB); output verified identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
