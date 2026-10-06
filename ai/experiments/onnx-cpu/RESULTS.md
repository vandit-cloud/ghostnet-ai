# ONNX Runtime on CPU: parity and latency

5 Oct 2026, branch `feat/onnx-cpu`. Models: gv5-yolo11s detector (`ghostnet.pt`,
sha256 `4ba7703e…`) and gvU1n-unet-hardneg-s1 net U-Net (`ghostnet_net.pt`,
`4a7aca46…`). Laptop: AMD Ryzen 7 7435HS (8 cores / 16 threads), RTX 3050
Laptop 4 GB, torch 2.13.0+cu126, onnxruntime 1.30.0 (CPUExecutionProvider),
ultralytics 8.4.134. Exports: FP32, opset 17, dynamic batch.

## Verdict

**ONNX on CPU is 1.4x faster than torch on CPU for the full stack (0.44 vs
0.61 s/tile), and the gain is all the U-Net.** The detector alone is a wash:
it is within noise of torch-CPU (0.12-0.15 s/tile either way). The GPU stays
7x faster than either (0.065 s/tile), so `auto` keeps torch whenever there is
a GPU. Outputs are the same as torch: on the 40-tile demo survey the payloads
matched exactly (0 of 40 frames differed, detector + U-Net).

## Parity (gates passed; export_onnx.py refuses on failure)

Reference is torch on CPU in FP32, the same arithmetic as the export, so any
difference is the export's.

| model | images | gate | result |
|---|---|---|---|
| detector | 200 val (`E:/New folder/ai/data/processed/val/images`, spread over the sorted list), conf 0.03 | same class, IoU >= 0.95, \|score delta\| <= 0.01 | **253/253 boxes paired, min IoU 0.99999, max score delta < 5e-6** |
| U-Net | 60 val + 11 net test chips (`net_seg_hardneg/test`); 24 of the 71 hold net pixels | Dice >= 0.99 per image at pixel threshold 0.5 | **min Dice 1.000, max probability delta 1e-5, blob count equal on 71/71** |

For information, the same detector comparison against the SHIPPED GPU path
(torch-CUDA FP16, a different computation) is outside the gate on 4 of 252
boxes: 3 small boxes whose IoU fell to 0.92-0.95 at identical scores, and one
NMS swap (0.047 vs 0.077). All four score 0.05-0.11 raw, at or below the 0.10
reporting floor. FP16 vs FP32 rather than ONNX vs torch; recorded in the
sidecar under `parity.vs_torch_cuda_fp16`.

## Latency

`ai/scripts/bench_runtime.py`: `infer.detect_batch` over 40 different 640x640
val tiles, median of 3 timed passes after a 2-batch warm-up, batch size 8.
That is decode + model + every post-processing step (dropout, shadow, edge
slivers, geotagging), i.e. what a user waits for. "Model-only" is
`_predict_many` on one tile per call: Ultralytics' letterbox + inference + NMS,
which is what published "ms per tile" figures usually mean.

| runtime | detector only, s/tile | detector + U-Net, s/tile | detector model-only, batch 1 |
|---|---|---|---|
| torch CUDA (FP16) | 0.021 | **0.065** | 27 ms |
| torch CPU (FP32) | 0.145 | 0.613 | 140 ms |
| ONNX Runtime CPU (FP32) | 0.150 | **0.437** | 104-110 ms |

Batch-size sweep on CPU (detector only, 2 passes each), to check the
`batch_size=8` default is not hurting the CPU path:

| batch | 1 | 2 | 4 | 8 |
|---|---|---|---|---|
| ONNX CPU s/tile | 0.118 | 0.124 | 0.130 | 0.131 |
| torch CPU s/tile | 0.156 | 0.134 | 0.116 | 0.119 |

Batching buys nothing on a CPU (the GPU's 18x comes from leaving its idle
clock, which a CPU does not have), and ONNX is ~10% better at batch 1 than
at 8. That is inside this machine's run-to-run noise (torch-CPU batch 8 read
0.145 in the first run and 0.119 in this one), so the default was NOT changed.

Demo survey end to end (`detect_survey` on `demo/NBP0505_line01B_demo.xtf`,
40 tiles, including XTF decode, tiling and the first model load): torch-CPU
35.5 s (0.89 s/tile), ONNX-CPU 24.5 s (0.61 s/tile), and 20.8 s on a second
ONNX run with a warm file cache.

## Against the numbers we had

* **Memory note 29 Sep: torch CPU full stack 1.34-1.61 s/frame.** Measured
  here in isolation it is 0.61 s/tile. That figure was taken through the
  running backend, where the venv's torch was CPU-only at the time and the
  model shares the CPU with uvicorn and the database; not re-measured there.
  Compare like with like: on the same harness ONNX takes 29% off.
* **Rival claim: ~90 ms/tile for YOLOv8s on ONNX CPU.** Our detector is
  104-110 ms/tile model-only on this CPU. YOLO11s is 21.4 GFLOPs to YOLOv8s'
  28.6, so on the same hardware ours should be no slower; the claim names no
  CPU, so the gap is most likely hardware. The honest difference is that our
  pipeline also runs a ResNet-34 U-Net for ghost_net (~0.29 s/tile on ONNX),
  which a box detector alone does not pay -- and which is what makes ghost_net
  findable at all (detector net recall 0.000; U-Net centroid 0.807).

## What would make CPU faster, not done

* INT8 dynamic quantisation of the U-Net encoder: probably 1.5-2x, but it
  changes outputs, so it needs its own parity gate on the 11 net test chips
  (Dice and centroid, not bit-match) before it could ship.
* A smaller U-Net encoder (resnet18): a retrain, outside this change.
* Running the U-Net only on tiles the dark-ridge filter flags (89% of held-out
  chains at 20% of the frame, ridge-filter-candidates): ~4x fewer U-Net calls,
  but a recall decision, not a runtime one.

## Reproduce

    python ai/scripts/export_onnx.py --images "E:/New folder/ai/data/processed/val/images" \
        --net-images "E:/New folder/ai/data/net_seg_hardneg/test/images" --n 200
    python ai/scripts/bench_runtime.py --images "E:/New folder/ai/data/processed/val/images"
