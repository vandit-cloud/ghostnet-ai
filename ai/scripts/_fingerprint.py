"""Dataset fingerprints, so "the split did not move" is checkable rather than hoped.

Why this exists
---------------
`docs/EXPERIMENT_GV7_PLAN.md` section 1.5 requires every run to assert that the
TEST split is byte-identical to the one gv5 was scored on, before training
starts. That assertion had no implementation: `build_report.json` carried no
`dataset_version` key at all, so the guard the plan describes could not run.

The failure it guards against is real and has happened. A source with no
SPLIT_POLICY entry falls through to the random pool, and adding a member to that
pool RE-DRAWS every other member -- importing PLANE-HAND moved ghost_net's test
boxes 36 -> 38 and wreck's 836 -> 837. Different boxes, not merely more. Every
comparison across that boundary was silently invalid.

What is fingerprinted, and why only the test split
--------------------------------------------------
The test split is the ruler. Train and val may grow between runs -- gv6 added
1,364 synthetic frames to train on purpose -- without invalidating a comparison,
so long as the thing being measured against did not move. So `dataset_version`
is keyed on test alone, and train/val sizes are recorded beside it for context
rather than folded into the hash.

Two separate digests, because they fail differently:

* `image_list` -- the sorted basenames. Catches a frame added, removed or
  renamed, which is the split-perturbation failure above.
* `label_content` -- the concatenated label bytes, in sorted filename order.
  Catches a re-annotation: same frames, different boxes. That is what a label
  audit does, and section 3.1 requires it to be an announced, one-time event
  rather than a silent drift.

This module is the canonical implementation. A shell one-liner over `find` and
`sha256sum` will NOT reproduce these digests -- sort order is locale-dependent
and the newline handling differs. Compare Python to Python.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")


def _image_names(split_dir: Path) -> list[str]:
    images = split_dir / "images"
    if not images.is_dir():
        return []
    return sorted(p.name for p in images.iterdir()
                  if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)


def _label_paths(split_dir: Path) -> list[Path]:
    labels = split_dir / "labels"
    if not labels.is_dir():
        return []
    return sorted((p for p in labels.iterdir() if p.suffix == ".txt"),
                  key=lambda p: p.name)


def fingerprint_split(root: Path, split: str) -> dict:
    """Digests and counts for one split. Missing split -> zeros, never raises."""
    split_dir = Path(root) / split

    names = _image_names(split_dir)
    h_names = hashlib.sha256()
    for n in names:
        h_names.update(n.encode("utf-8"))
        h_names.update(b"\n")

    label_paths = _label_paths(split_dir)
    h_labels = hashlib.sha256()
    empty = 0
    for p in label_paths:
        body = p.read_bytes()
        if not body.strip():
            empty += 1
        # The name goes into the digest too: without it, moving a box from one
        # frame to another would leave the concatenation unchanged.
        h_labels.update(p.name.encode("utf-8"))
        h_labels.update(b"\0")
        h_labels.update(body)
        h_labels.update(b"\n")

    return {
        "n_images": len(names),
        "n_labels": len(label_paths),
        "n_background": empty,
        "image_list": h_names.hexdigest(),
        "label_content": h_labels.hexdigest(),
    }


def fingerprint_dataset(root: Path) -> dict:
    """All three splits, plus the compact `dataset_version` string."""
    root = Path(root)
    per_split = {s: fingerprint_split(root, s) for s in ("train", "val", "test")}
    test = per_split["test"]

    # Keyed on test alone -- see the module docstring. Short prefix is for
    # reading in a log line; the full digests stay in `splits` for the assert.
    version = "test%d-%s" % (test["n_images"], test["image_list"][:12])

    return {
        "dataset_version": version,
        "splits": per_split,
        "note": ("dataset_version is keyed on the TEST split only, because test is the "
                 "ruler and train/val are allowed to grow. Compare `splits.test` digests "
                 "to assert comparability with an earlier run."),
    }


def read_expected(root: Path) -> dict | None:
    """The fingerprint recorded in build_report.json, or None if absent."""
    report = Path(root) / "build_report.json"
    if not report.is_file():
        return None
    try:
        data = json.loads(report.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    fp = data.get("fingerprints")
    return fp if isinstance(fp, dict) else None


def check_test_split(root: Path) -> tuple[bool, list[str]]:
    """Recompute the test split and compare against build_report.json.

    Returns (ok, messages). Not-recorded is reported as a problem rather than a
    pass: a run that cannot assert comparability must say so, per plan 1.5.
    """
    root = Path(root)
    expected = read_expected(root)
    if expected is None:
        return False, [
            "build_report.json carries no `fingerprints` block, so this dataset "
            "cannot be asserted comparable to an earlier run.",
            "Run: python ai/scripts/verify_dataset.py --write",
        ]

    want = (expected.get("splits") or {}).get("test") or {}
    got = fingerprint_split(root, "test")

    problems: list[str] = []
    for key, label in (("n_images", "test image count"),
                       ("image_list", "test image-list digest"),
                       ("label_content", "test label-content digest")):
        if key not in want:
            problems.append(f"{label}: not recorded in build_report.json")
        elif want[key] != got[key]:
            problems.append(f"{label} CHANGED: recorded {want[key]}, on disk {got[key]}")

    if problems:
        problems.append("The test split is the ruler. A run measured against a moved "
                        "ruler is not comparable to gv1-gv6 and must not be promoted.")
    return (not problems), problems
