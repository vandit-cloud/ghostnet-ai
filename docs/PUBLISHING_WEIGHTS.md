# Publishing the trained weights

The trained models are not published. This file is the checklist for the day
the owner decides to publish them. It is the owner's decision, not a
contributor's: nothing in this repository uploads weights on its own, and
`ai/scripts/fetch_weights.py --trained` has no default URL until this is done.

| File | Model | Size |
|---|---|---|
| `ai/models/trained/ghostnet.pt` | gv5-yolo11s box detector | 19 MB |
| `ai/models/trained/ghostnet_net.pt` | gvU1n-unet-hardneg-s1 net U-Net | 98 MB |
| `*.onnx` beside each | verified ONNX exports (`ai/scripts/export_onnx.py`) | |

> **Known exposure.** `ghostnet.pt` was committed in the initial import
> (18 Sep 2026, `353cd51`) and is in the history of the public repository,
> although its sidecar says it is gitignored. Settle that before anything
> else on this list. The U-Net was never committed.

## 1. Decide whether the training data allows it

Weights are derived from their training images. Whether a licence reaches
through to a model is legally unsettled, so read each row below as "what the
source permits for redistribution", and decide on the most restrictive row.

gv5 trained on 8 sources (`ai/experiments/gv5-yolo11s/provenance.json`):

| Source | Images | Licence on record | Concern |
|---|---|---|---|
| AI4SHIPWRECKS | 6,976 | "open research dataset", no licence file | Unstated terms |
| GHOSTVISION | 6,655 | CC BY-SA 4.0 | **Share-alike**: derived weights may have to be released CC BY-SA too |
| CHINA-OFFSHORE | 2,072 | CC BY 4.0 | Attribution |
| SUBPIPE | 2,049 | CC BY 4.0 | Attribution |
| SCTD | 327 | Not stated; the paper says academic use | **Academic use only** |
| MARINE-PULSE | 88 | Not stated on the Zenodo record | Unstated terms |
| GHOSTNET-HAND | 73 | Imagery CC BY 4.0 (China Offshore HN class); our annotations CC BY 4.0 | Attribution |
| SONARDETECT | 70 | CC BY 4.0 on Roboflow | Its frames are slides and screenshots of other people's images, so the CC BY label may not be the uploader's to give |

The U-Net trained on `net_seg_hardneg` (China Offshore net chips plus mined
hard negatives). Check where the hard negatives came from before treating it
as CC BY only.

Consequences of the rows above:

- **SCTD is academic-use-only and is the binding row.** A non-commercial
  research release is the most it clearly allows. If that is too narrow,
  retrain without SCTD (327 images, 1.8% of the data) first.
- **GhostVision is CC BY-SA.** The cautious reading releases the detector
  under CC BY-SA 4.0 as well, which is compatible with research use.
- **The KLSG hand-labelling bundle (5 Oct) is academic use, no
  redistribution.** Any model trained on it inherits the SCTD-style limit.

## 2. Attribution

Ship an `ATTRIBUTION` section with the weights (model card or release notes)
citing every source above. `ATTRIBUTION.md` at the repo root covers the
redistributed frames; the weights need their own list, because they derive
from all 18,310 training images, not only the redistributed ones.

## 3. Publish

1. Pick a host where the URL shape is `<base>/<filename>`:
   Hugging Face (`https://huggingface.co/<org>/<repo>/resolve/main`) or a
   GitHub release (`https://github.com/<org>/<repo>/releases/download/<tag>`).
2. Upload each `.pt`, `.onnx` and its sidecar (`ghostnet.json`,
   `ghostnet_net.json`, `*.onnx.json`).
3. Commit the sidecars to git. `fetch_weights.py` checks every download
   against the sha256 in a sidecar that is already on disk. A sidecar from git
   proves the file is the one this code was released with; one downloaded
   from the same server only proves the transfer was not corrupted.
4. Set `DEFAULT_WEIGHTS_URL` in `ai/scripts/fetch_weights.py` and
   `WEIGHTS_URL` in `notebooks/quickstart.ipynb`.
5. Check it from a clean clone:
   `python ai/scripts/fetch_weights.py --trained --with-onnx`.

## 4. Model card, minimum

State the measured numbers with their test sets, not a headline: mAP50 0.352
on the 4,346-frame frozen test split; ghost_net found at 0.000 on real nets
by the detector (the U-Net carries that class, review-only); U-Net figures on
11 chips from 2 sites, 10 of them from one. Say that the model has not seen
Indian waters.
