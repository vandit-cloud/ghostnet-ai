"""Download the weights that git deliberately does not carry.

    python ai/scripts/fetch_weights.py                       # pretrained YOLO bases (training)
    python ai/scripts/fetch_weights.py --trained --url URL   # the served GhostNet models
    python ai/scripts/fetch_weights.py --trained --url URL --with-onnx --only detector

PRETRAINED (the default, unchanged)
-----------------------------------
Weights are build inputs, not source. Committing them makes every clone and
every branch switch drag tens of megabytes around for files that are
byte-identical and freely re-downloadable. Ultralytics resolves these names
against its own release assets, so this is the same download the library
would do implicitly on first use -- made explicit, so a fresh clone can be
prepared offline before a demo instead of discovering the need for a network
connection five minutes beforehand.

TRAINED (--trained)
-------------------
The served models -- ghostnet.pt (detector), ghostnet_net.pt (net U-Net) and,
with --with-onnx, their verified ONNX exports -- from wherever they were
published: `--url`, or GHOSTNET_WEIGHTS_URL. Each file is fetched as
`<url>/<filename>`, which is the shape of both a Hugging Face model repo
(https://huggingface.co/<org>/<repo>/resolve/main) and a GitHub release
(https://github.com/<org>/<repo>/releases/download/<tag>). Nothing is
published yet: docs/PUBLISHING_WEIGHTS.md is the checklist, and it is the
owner's decision.

Every weights file is checked against the sha256 in its SIDECAR before it is
put in place: `<stem>.json` -> "sha256" for a .pt, `<stem>.onnx.json` ->
"onnx_sha256" for an .onnx. A sidecar already on disk WINS over a downloaded
one, and that is the point: ai/models/trained/ghostnet.json is committed to
git, so the hash a download is held to comes from the repository, not from
the same server that served the file. A sidecar fetched alongside its weights
only proves the transfer was not corrupted; one from git proves it is the
model the code was released with. A mismatch deletes the download and fails.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
DEST = AI_ROOT / "models" / "pretrained"
TRAINED = AI_ROOT / "models" / "trained"

# yolo11n for fast iteration, yolo11s as the 4 GB-VRAM training target.
# yolo11s-seg is the Track D / D2 ghost_net segmentation backbone: a net is a
# long thin fragmented shape that a box describes badly, so that class trains as
# a single-class segmentation model of its own. See EXPERIMENT_GV7_PLAN.md 10.2.
# yolo11s-cls backs the chip-level `natural` classifier -- a gully field has no
# discrete object to box, so that question is a whole-chip one. It is a SECOND
# STAGE beside the detector, never a detector class; see train_natural.py.
WEIGHTS = ["yolo11n.pt", "yolo11s.pt", "yolo11s-seg.pt", "yolo11s-cls.pt"]

#: The served models, by the stem config.py resolves them under.
TRAINED_STEMS = {"detector": "ghostnet", "net": "ghostnet_net"}

#: Set this when the weights are published (docs/PUBLISHING_WEIGHTS.md), so a
#: bare `--trained` works. None until then, on purpose: a default pointing at
#: a location that does not exist yet fails in a more confusing way than this.
DEFAULT_WEIGHTS_URL: str | None = None


# ---------------------------------------------------------------- trained

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sidecar_for(weights_name: str) -> tuple[str, str]:
    """(sidecar filename, key holding the expected sha256) for a weights file."""
    if weights_name.endswith(".onnx"):
        return weights_name + ".json", "onnx_sha256"
    return Path(weights_name).with_suffix(".json").name, "sha256"


def expected_sha256(sidecar: Path, key: str) -> str | None:
    try:
        value = json.loads(sidecar.read_text(encoding="utf-8")).get(key)
    except (OSError, ValueError):
        return None
    return value if isinstance(value, str) and len(value) == 64 else None


def download(url: str, target: Path) -> None:
    """Stream `url` to `target` through a .part file, so an interrupted
    download never leaves a truncated file under the real name."""
    part = target.with_name(target.name + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "ghostnet-fetch-weights"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(part, "wb") as out:
        shutil.copyfileobj(resp, out, length=1 << 20)
    part.replace(target)


def fetch_verified(base_url: str, name: str, dest_dir: Path, fetch=download) -> str:
    """Fetch one weights file and its sidecar into dest_dir, verified.

    Returns a one-line status. Raises ValueError on a hash mismatch, after
    deleting the bad download. `fetch` is injectable for tests.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    side_name, key = sidecar_for(name)
    side = dest_dir / side_name
    target = dest_dir / name
    side_source = "local"
    if not side.exists():
        fetch(f"{base_url.rstrip('/')}/{side_name}", side)
        side_source = "downloaded"
    want = expected_sha256(side, key)
    if want is None:
        raise ValueError(f"{side_name} has no usable '{key}'; cannot verify {name}")
    if target.exists() and sha256(target) == want:
        return f"have     {name}  (sha256 matches {side_source} {side_name})"
    tmp = dest_dir / (name + ".download")
    try:
        fetch(f"{base_url.rstrip('/')}/{name}", tmp)
        got = sha256(tmp)
        if got != want:
            raise ValueError(f"{name}: sha256 {got[:12]}... does not match {side_name} "
                             f"({want[:12]}...); download discarded")
        tmp.replace(target)
    finally:
        if tmp.exists():
            tmp.unlink()
    return f"verified {name}  ({target.stat().st_size / 1e6:.1f} MB, sha256 matches {side_source} {side_name})"


def fetch_trained(base_url: str, only: str | None, with_onnx: bool, dest_dir: Path = TRAINED) -> int:
    names = []
    for kind, stem in TRAINED_STEMS.items():
        if only and kind != only:
            continue
        names.append(stem + ".pt")
        if with_onnx:
            names.append(stem + ".onnx")
    status = 0
    for name in names:
        try:
            print(fetch_verified(base_url, name, dest_dir))
        except ValueError as exc:
            print("REFUSED  " + str(exc))
            status = 1
        except OSError as exc:      # urllib errors are OSErrors
            print(f"FAILED   {name}: {exc}")
            status = 1
    return status


# ------------------------------------------------------------- pretrained

def fetch_pretrained() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    try:
        from ultralytics import YOLO
    except ImportError:
        print("ultralytics is not installed. Run: pip install -r ai/requirements.txt")
        return 1

    for name in WEIGHTS:
        target = DEST / name
        if target.exists():
            print("have    " + name + "  (" + str(round(target.stat().st_size / 1e6, 1)) + " MB)")
            continue
        print("fetching " + name + " ...")
        # YOLO() downloads into the ultralytics cache, wherever that is; move
        # the file to our own tree so the path is stable across machines.
        model = YOLO(name)
        src = Path(getattr(model, "ckpt_path", "") or name)
        if src.exists() and src.resolve() != target.resolve():
            shutil.move(str(src), str(target))
        if target.exists():
            print("saved   " + str(target.relative_to(AI_ROOT.parent)))
        else:
            print("WARNING could not place " + name + " into " + str(DEST))

    missing = [w for w in WEIGHTS if not (DEST / w).exists()]
    if missing:
        print("missing: " + ", ".join(missing))
        return 1
    print("all pretrained weights present in ai/models/pretrained/")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trained", action="store_true", help="fetch the served GhostNet models, not the YOLO bases")
    ap.add_argument("--url", help="base URL the trained weights were published under "
                                  "(default: GHOSTNET_WEIGHTS_URL)")
    ap.add_argument("--only", choices=tuple(TRAINED_STEMS), help="just one of the two models")
    ap.add_argument("--with-onnx", action="store_true", help="also fetch the verified ONNX exports (CPU runtime)")
    ap.add_argument("--dest", default=str(TRAINED), help="target folder (default ai/models/trained)")
    args = ap.parse_args(argv)

    if not args.trained:
        return fetch_pretrained()
    url = args.url or os.environ.get("GHOSTNET_WEIGHTS_URL") or DEFAULT_WEIGHTS_URL
    if not url:
        print("No weights URL. Pass --url or set GHOSTNET_WEIGHTS_URL. The trained weights are not "
              "published by default; see docs/PUBLISHING_WEIGHTS.md.")
        return 1
    return fetch_trained(url, args.only, args.with_onnx, Path(args.dest))


if __name__ == "__main__":
    sys.exit(main())
