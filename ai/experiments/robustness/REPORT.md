# Robustness report

Generated 2026-09-26T17:10 UTC by `ai/scripts/robustness_report.py` (commit `d5b22c3`). Weights `ghostnet.pt` (gv5-yolo11s); test split `test4346-8bfbcc102487`, 4346 images, 2930 carrying no annotation.

Harness check, clean row against gv5's record: REPRODUCED — mAP50 0.3525 (recorded 0.3525), empty-seabed rate 7.82% (recorded 7.82%)

| condition | mAP50 | Δ | recall | Δ | wreck R | plane R | debris R | ghost_pot R | ghost_net R | empty-seabed false alarms @ raw 0.10 | Δ |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `clean` | 0.352 | +0.000 | 0.361 | +0.000 | 0.316 | 0.333 | 0.855 | 0.300 | 0.000 | 7.82% (229/2930) | +0.00 pp |
| `speckle_0.20` | 0.310 | -0.042 | 0.316 | -0.045 | 0.294 | 0.250 | 0.852 | 0.183 | 0.000 | 4.91% (144/2930) | -2.90 pp |
| `speckle_0.35` | 0.263 | -0.090 | 0.246 | -0.115 | 0.184 | 0.222 | 0.817 | 0.007 | 0.000 | 2.32% (68/2930) | -5.49 pp |
| `speckle_0.50` | 0.221 | -0.132 | 0.212 | -0.149 | 0.104 | 0.222 | 0.734 | 0.000 | 0.000 | 1.37% (40/2930) | -6.45 pp |
| `contrast_0.50` | 0.305 | -0.047 | 0.313 | -0.048 | 0.321 | 0.222 | 0.620 | 0.404 | 0.000 | 5.84% (171/2930) | -1.98 pp |
| `contrast_0.25` | 0.085 | -0.267 | 0.115 | -0.245 | 0.112 | 0.111 | 0.011 | 0.342 | 0.000 | 3.65% (107/2930) | -4.16 pp |
| `blur_9` | 0.206 | -0.146 | 0.228 | -0.133 | 0.024 | 0.222 | 0.627 | 0.268 | 0.000 | 9.97% (292/2930) | +2.15 pp |
| `blur_21` | 0.061 | -0.292 | 0.083 | -0.277 | 0.004 | 0.111 | 0.038 | 0.265 | 0.000 | 5.80% (170/2930) | -2.01 pp |
| `dropout_10` | 0.099 | -0.254 | 0.243 | -0.118 | 0.233 | 0.111 | 0.614 | 0.257 | 0.000 | 26.42% (774/2930) | +18.60 pp |

Per-class recall is Ultralytics' at its default operating point. `plane` has 9 test boxes and `ghost_net` 36: do not read a trend off either.

## Recorded clean-data evidence, for the same table

- Empty-seabed false alarms, clean, raw gate 0.10: 7.82% (229 tiles) — `ai/experiments/gv5-yolo11s/background_metrics.json`
- Wreck recall by share of frame: <0.2% 0.112 (16/143), 0.2-0.5% 0.060 (11/184), 0.5-2% 0.075 (13/174), >2% 0.525 (176/335) — `ai/experiments/gv5-yolo11s/wreck_recall_by_size.json`
- ghost_net U-Net (gvU1n, 3 seeds): fires on 1.3% of empty seabed chips, on China-Offshore only; 11 test chips — `ai/experiments/unet-scoring/RESULTS.md`. Not re-measured under degradation here: 11 chips cannot carry a curve.

Degradations, seeds and what is not measured: see the module docstring.
