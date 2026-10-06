"""False-alarm rate of a ghost_net segmentation model on EMPTY seabed.

    python ai/scripts/evaluate_net_negatives.py --weights <best.pt>
    python ai/scripts/evaluate_net_negatives.py --weights <best.pt> --out result.json

Reads ai/data/net_seg_hardneg/neg_holdout/images -- China-Offshore natural
seabed chips from the val/test splits, never trained on (build_net_seg_hardneg.py).

Every chip here has no net, so every predicted outline is a false alarm. This
is the number the 11-chip test split cannot give: its chips all contain nets,
so precision there only counts mistakes made next to real nets.

Reported at the threshold the app ships (0.25) and one stricter one, per
seabed type, because "fires on trench/gully" and "fires on sand" call for
different fixes.
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

DEFAULT_DIR = Path("E:/New folder/ai/data/net_seg_hardneg/neg_holdout/images")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--weights", required=True)
    ap.add_argument("--images", type=Path, default=DEFAULT_DIR)
    ap.add_argument("--conf", type=float, nargs="+", default=[0.25, 0.5])
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()

    from ultralytics import YOLO

    model = YOLO(a.weights)
    images = sorted(a.images.glob("*"))
    lo = min(a.conf)
    per_image = {}
    for p in images:
        r = model.predict(str(p), conf=lo, imgsz=640, device=a.device, retina_masks=False, verbose=False)[0]
        per_image[p.name] = [float(c) for c in r.boxes.conf.tolist()] if r.boxes is not None else []

    def group(name: str) -> str:
        return name.split("__")[1].rsplit("_", 1)[0]

    result = {"weights": a.weights, "images": len(images), "by_conf": {}}
    for c in a.conf:
        fired = {k: sum(s >= c for s in v) for k, v in per_image.items()}
        by = collections.defaultdict(lambda: [0, 0])
        for k, n in fired.items():
            by[group(k)][0] += 1
            by[group(k)][1] += n > 0
        result["by_conf"][str(c)] = {
            "frames_with_false_alarm": sum(n > 0 for n in fired.values()),
            "false_alarm_frame_rate": round(sum(n > 0 for n in fired.values()) / max(len(images), 1), 3),
            "false_outlines_per_frame": round(sum(fired.values()) / max(len(images), 1), 3),
            "by_group": {g: f"{hit}/{tot}" for g, (tot, hit) in sorted(by.items())},
        }
        r = result["by_conf"][str(c)]
        print(f"conf {c}: {r['frames_with_false_alarm']}/{len(images)} empty chips fire "
              f"({r['false_alarm_frame_rate']:.0%}), {r['false_outlines_per_frame']} false outlines/chip")
        print("   by seabed type (fired/total):", r["by_group"])
    if a.out:
        a.out.write_text(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
