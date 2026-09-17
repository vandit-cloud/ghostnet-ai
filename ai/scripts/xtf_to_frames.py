"""Turn a real .xtf survey file into frames the pipeline can run on.

    python ai/scripts/xtf_to_frames.py --xtf path/to/survey.xtf --out E:/xtf-run
    python ai/scripts/xtf_to_frames.py --xtf survey.xtf --frames 4 --detect

Writes <out>/frame_XXXX.png plus a matching frame_XXXX.json of survey metadata
in the shape ghostnet.detect() already accepts. With --detect it runs the
pipeline too and writes report.csv, which is the whole problem statement in one
command: a sonar file goes in, geotagged anomalies come out.

Why the metadata is written as a sidecar rather than passed straight through
---------------------------------------------------------------------------
Nothing else in this project has ever seen real survey metadata -- every
position so far came from a hand-written example file. Writing the sidecar
makes what the sonar actually recorded inspectable next to the frame it
describes, so a wrong coordinate can be traced to the ping that produced it
rather than argued about. It is also exactly the file `try_model.py --meta`
already takes, so the two paths stay one path.

One frame is many pings
-----------------------
A ping is one row. A frame is a stack of them, and the stack is what a detector
sees. Navigation is taken from the MIDDLE ping of each stack rather than the
first, because the frame's coordinate should describe its centre; using the
first biases every position half a frame astern, which at 800 pings is a
systematic offset no error bar accounts for.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))


def main() -> int:
    ap = argparse.ArgumentParser(description="Convert an XTF survey into frames plus metadata.")
    ap.add_argument("--xtf", required=True)
    ap.add_argument("--out", default=str(AI_ROOT / "experiments" / "xtf_run"))
    ap.add_argument("--pings-per-frame", type=int, default=800)
    ap.add_argument("--frames", type=int, default=4)
    ap.add_argument("--skip", type=int, default=200,
                    help="pings to discard first; deployment pings carry no altitude")
    ap.add_argument("--detect", action="store_true", help="also run the pipeline and write report.csv")
    args = ap.parse_args()

    import cv2

    from ghostnet.xtf import geometry_for, iter_pings, read_file_header, waterfall

    src = Path(args.xtf)
    header = read_file_header(src)
    print()
    print(f"  {src.name}")
    print(f"  sonar {header.sonar_name!r} recorded by {header.recording_program!r}")
    print(f"  nav units {header.nav_units} "
          f"({'degrees' if header.nav_is_degrees else 'NOT degrees'}), "
          f"{header.bytes_per_sample} bytes/sample")

    if not header.nav_is_degrees:
        print("\n  refusing: navigation is not in degrees, so latitude/longitude cannot be")
        print("  read directly and this reader will not guess a projection.")
        return 1

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    need = args.skip + args.pings_per_frame * args.frames
    pings = list(iter_pings(src, header, with_samples=True, limit=need))[args.skip:]
    print(f"  {len(pings)} pings after skipping {args.skip}\n")

    payloads = []
    written = 0
    for i in range(args.frames):
        block = pings[i * args.pings_per_frame : (i + 1) * args.pings_per_frame]
        if len(block) < args.pings_per_frame // 2:
            break
        img = waterfall(block)
        if img.size == 0:
            continue

        mid = block[len(block) // 2]
        stem = f"frame_{i:04d}"
        cv2.imwrite(str(out / f"{stem}.png"), img)

        # Along-track metres per row: distance the fish covers between pings.
        # Left as None unless the file gives a ping rate, rather than assumed.
        along = None
        geom = geometry_for(mid, image_width=img.shape[1], along_track_res_m=along)
        meta = {
            "survey_id": src.stem,
            "frame_id": stem,
            "_source": {
                "xtf": str(src), "sonar": header.sonar_name,
                "pings": [block[0].ping_number, block[-1].ping_number],
                "time": mid.time, "depth_m": round(mid.depth_m, 2),
            },
        }
        if geom is not None:
            meta.update({
                "latitude": mid.latitude, "longitude": mid.longitude,
                "heading_deg": geom.heading_deg, "altitude_m": geom.altitude_m,
                "nadir_col": geom.nadir_col,
                "range_resolution_m": geom.range_resolution_m,
                "layback_m": geom.layback_m,
            })
        else:
            meta["_no_geometry"] = ("this frame's centre ping carries no usable altitude, "
                                   "so no position is claimed for it")
        (out / f"{stem}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

        note = "geotagged" if geom is not None else "NO GEOMETRY"
        print(f"  {stem}.png  {img.shape[1]}x{img.shape[0]}  "
              f"pings {block[0].ping_number}-{block[-1].ping_number}  {note}")
        written += 1

        if args.detect:
            from ghostnet import detect

            payload = detect(str(out / f"{stem}.png"), meta)
            payloads.append(payload)
            for d in payload.get("detections") or []:
                pos = (f"{d['latitude']:.6f}, {d['longitude']:.6f} "
                       f"+/-{d['position_error_m']} m" if d.get("latitude") is not None
                       else "no position")
                print(f"        {d['class']:9s} conf {d['calibrated_confidence']:.2f}   {pos}")

    if args.detect and payloads:
        from ghostnet.report import write_csv

        csv_path = write_csv(payloads, out / "report.csv")
        found = sum(len(p.get("detections") or []) for p in payloads)
        print(f"\n  {found} detections across {len(payloads)} frames")
        print(f"  {csv_path}")

    print(f"\n  wrote {written} frames to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
