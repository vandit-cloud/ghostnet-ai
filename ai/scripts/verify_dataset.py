"""Assert the test split has not moved. Run this before every training run.

    python ai/scripts/verify_dataset.py            # check, exit 1 on drift
    python ai/scripts/verify_dataset.py --write    # record the current state

`--write` backfills the `fingerprints` block into an existing
`build_report.json` WITHOUT rebuilding anything. That matters: re-running
build_dataset.py to get a fingerprint would re-draw the splits, which is the
exact accident the fingerprint exists to detect.

See docs/EXPERIMENT_GV7_PLAN.md section 1.5.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT / "scripts"))

from _fingerprint import check_test_split, fingerprint_dataset  # noqa: E402

PROCESSED = AI_ROOT / "data" / "processed"


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify the test split is unchanged.")
    ap.add_argument("--root", default=str(PROCESSED))
    ap.add_argument("--write", action="store_true",
                    help="record the current fingerprints into build_report.json")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        print(f"no dataset at {root}")
        return 1

    fp = fingerprint_dataset(root)
    test = fp["splits"]["test"]

    print(f"\n  dataset_version  {fp['dataset_version']}")
    for split in ("train", "val", "test"):
        s = fp["splits"][split]
        print(f"  {split:<6} {s['n_images']:>6} images  {s['n_labels']:>6} labels  "
              f"{s['n_background']:>6} background")
    print(f"\n  test image-list     {test['image_list']}")
    print(f"  test label-content  {test['label_content']}")

    report_path = root / "build_report.json"

    if args.write:
        if not report_path.is_file():
            print(f"\nno build_report.json at {report_path}; nothing to backfill")
            return 1
        report = json.loads(report_path.read_text(encoding="utf-8"))
        had = "fingerprints" in report
        report["dataset_version"] = fp["dataset_version"]
        report["fingerprints"] = fp
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\n{'updated' if had else 'recorded'} fingerprints in {report_path.name}")

        # build_report.json lives beside the data and is gitignored with it, so
        # on its own it is not a record anyone else can check against. Mirror
        # the fingerprint into provenance/, which is tracked on purpose -- that
        # is what lets a second machine, or this one after a rebuild, tell
        # whether it holds the same ruler gv5 was scored on.
        provenance = AI_ROOT / "data" / "provenance"
        provenance.mkdir(parents=True, exist_ok=True)
        tracked = provenance / "dataset_fingerprint.json"
        tracked.write_text(json.dumps(fp, indent=2), encoding="utf-8")
        print(f"recorded tracked copy in {tracked.relative_to(AI_ROOT.parent)}")

        if had:
            print("NOTE: a previous fingerprint was overwritten. If that was not "
                  "deliberate, the comparison baseline has just been reset.")
        return 0

    ok, problems = check_test_split(root)
    if ok:
        print("\n  OK: test split matches build_report.json")
        return 0
    print("\n  DRIFT:")
    for p in problems:
        print(f"    - {p}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
