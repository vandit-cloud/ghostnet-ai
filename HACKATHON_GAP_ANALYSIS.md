# GhostNet-AI: Hackathon Gap Analysis & Winning Plan (SIH26057)

> **What this file is:** a comparison of the four strategy PDFs against the code in this repo (as of 26 Sep 2026). It lists what is built, what is half-built, what is missing, and what to build next to give the project the best chance of winning.
>
> **PDFs covered:**
> 1. `GhostNet-AI_Strategy_and_Architecture.pdf`: 25 ideas, "Detect → Verify → Localize → Prioritize", 5 signature modules
> 2. `GhostNet-AI_Alternative-Solution-Architecture.pdf`: anomaly engine, self-supervised learning, "three opinions", "See → Trust → Act"
> 3. `GhostNet-AI_SonarOps-Agent_Strategy.pdf`: a natural-language agent that runs the whole workflow
> 4. `GhostNet-AI_Trustworthy-Sonar-Intelligence.pdf`: domain shift, operational trust, abstention, coverage, re-scan, robustness benchmark

---

## 0. TL;DR

**The good news:** the project is already stronger than a typical "YOLO + dashboard" entry. It has:
- real XTF parsing
- slant-range geolocation with error circles
- temperature calibration
- asymmetric review floors
- dropout detection
- shadow evidence
- a U-Net second stage for ghost nets
- RBAC and an audit trail
- honest negative results (gv6, TTA)

The "honesty" culture in the repo is exactly what PDF 4 ("Trustworthy Sonar Intelligence") recommends, so the pitch direction and the codebase already agree.

**The gap:** all four PDFs push the same 5 things, and most of them are **missing or only partly built**:

| # | Signature module (in all 4 PDFs) | Status |
|---|---|---|
| 1 | **Evidence Fusion**: object + shadow + context + quality + track, combined into one verdict | 🟡 Evidence is *collected* but never *fused*. Right now it is only a text summary. |
| 2 | **CONFIRM / REVIEW / ABSTAIN gate** | 🟡 Pieces exist (`review_only`, uncertainty bands, suppression floors) but there is no explicit 3-state verdict |
| 3 | **Track-to-Map Fusion**: many frames become one target and one fused location | ❌ Not built. The code itself says duplicates at tile seams are not suppressed (`ai/ghostnet/survey.py:81-85`) |
| 4 | **Target Dossier / Passport** UI | 🟡 The detection detail page shows evidence as key/value rows. There is no dossier, "why flagged" or passport export. |
| 5 | **SonarOps Agent** (natural-language orchestrator) | ❌ Not built at all |

**Recommendation:** don't build all ~40 ideas. Build **modules 1–5 end-to-end**, plus two cheap "wow" add-ons (**Sonar Health gate** and **Coverage / Re-scan map**). Present everything else as roadmap. The pitch becomes:

> **"GhostNet-AI doesn't just detect objects. It decides whether the evidence is trustworthy, merges repeated sightings into one physical target with an honest location region, says 'I don't know' when it should, and an agent runs the whole survey for the operator."**

---

## 1. What the 4 PDFs say (condensed)

| PDF | Core message | Its top-5 "build these" |
|---|---|---|
| **Strategy & Architecture** | Turn "object detector" into an "evidence and decision system". | Acoustic Evidence Fusion · Confidence Gate · Track-to-Map Fusion · Target Evidence Dossier · Human Learning Loop |
| **Alternative Solution Architecture** | Change *how* the problem is solved: first ask "is this region anomalous vs. natural seabed?", then classify it. SEE → TRUST → ACT. | Sonar Anomaly Engine · YOLO + Evidence Fusion · Multi-frame Tracking + Geo Fusion · Confirm/Review/Abstain + Target Passport · SonarOps Agent |
| **SonarOps Agent** | An agent orchestrates the pipeline through **tools/API** (reliable), with a browser-driven version for the visible demo. It has an agent inbox, "ask the agent", graceful agentic degradation and permission levels. | Agent with tool layer · Mission plan · Agent inbox · Permission levels · `data-agent-action` hooks |
| **Trustworthy Sonar Intelligence** | The hard problem is *trust under shift*: new sonar, poor quality, unseen objects, uncertain location. Model confidence is not operational trust. | Universal Sonar Adaptation · Anthropogenic Evidence Fusion · Open-world / Abstaining detection · Track-to-Map Probabilistic Localization · Autonomous SonarOps Agent |

**Shared warnings in all 4 PDFs, which match the repo's own rules:**
- Never claim "first in the world" or "no one has solved this".
- Never present synthetic-on-synthetic numbers as field accuracy.
- Claim **the combination and the working implementation**, not any single idea.

---

## 2. Full status matrix: every idea vs. the code

Legend: ✅ Done · 🟡 Partial · ❌ Not built · ⛔ Tried and rejected (negative result, documented)

### 2.1 Data, preprocessing and sonar handling

| Idea (PDF) | Status | Evidence in repo | What's missing |
|---|---|---|---|
| XTF ingest + validation | ✅ | `ai/ghostnet/xtf.py`, `app/backend/app/services/xtf_ingest.py` | JSF format (no sample data) |
| Geometry from ping headers (nadir, range res, altitude, heading) | ✅ | `ai/ghostnet/survey.py`, `xtf.py` | — |
| Port/starboard canonicalization (PDF1 #16) | ✅ | Per-channel sample-order fix (KNOWN_ISSUES F1), `ai/tests/test_waterfall_orientation.py` | — |
| Overlapping tile inference (PDF1 #14) | 🟡 | Tiles are 640 px; only the *last* tile overlaps (`survey.py:_tile_starts`) | Real overlap on every tile, plus merging duplicates in **survey coordinates** (NMS). The code comment says this is "not done here". |
| Range-aware preprocessing (PDF1 #15) | ❌ | Only a uniform `preprocess.py` | Near / mid / far range normalization or thresholds |
| Dropout detection (PDF1 #6, PDF4 #11) | ✅ | `ai/ghostnet/dropout.py`: invalid rows, frame warning, per-box overlap, which escalates uncertainty | — |
| **Sonar Quality / Health Gate**: noise, contrast, dropout, shadow clarity, nav (PDF1 #6, PDF2 #10, PDF4 #11) | 🟡 | Dropout plus `SonarFrame.quality_status` (only `"ok"` / `"no_navigation"`) | Numeric per-segment **quality score** (noise, contrast, dropout %, nav availability) and a **GOOD / MODERATE / POOR** label that *changes inference behaviour* |
| Adaptive / quality-aware thresholds (PDF1 #7) | 🟡 | Class-specific floors (artificial 0.20, natural 0.45, net lower) in `decision.py` | Thresholds that depend on **sonar quality**, tuned on validation data |
| Sonar domain fingerprint / Universal Adapter / self-calibration (PDF4 #1–2) | ❌ | `dataset_fingerprint.json` is for dataset provenance, not runtime | Per-survey fingerprint (intensity histogram, speckle stats, resolution, frequency), a "domain match" score, and per-survey normalization |
| Two-stage inference: fast scan, then detailed (PDF1 #13) | 🟡 | Box detector + optional U-Net second stage for nets (`netseg.py`) | A true cheap first pass that picks candidate regions (only needed if speed is a problem, and it isn't: 40 frames take about 14 s) |
| Test-time augmentation | ⛔ | `ai/experiments/gv7.T-gv5-tta/notes.md`: recall −0.042, not shipped | Keep it as a negative result. It is a good answer when judges ask "did you try X?" |
| Synthetic ghost-net generation (PDF1 #17) | ⛔/✅ | `synth_ghost_net.py`; gv6 with synthetic data gave net recall 0.000 (`docs/EXPERIMENT_GV6.md`) | Already handled honestly (train-only, never quoted as field accuracy) |

### 2.2 Detection and verification (the "SEE" and "TRUST" layers)

| Idea | Status | Evidence | Missing |
|---|---|---|---|
| YOLO11-S detector, 5 training classes | ✅ | `infer.py`, `models/trained/ghostnet.pt` (gv5) | — |
| Ghost-net segmentation (U-Net) | ✅ | `unet.py`, `netseg.py`: Dice 0.600, centroid 0.807, 1.3 % empty-chip false alarms (11 test chips, 3 seeds) | More real net data (GhostNetZero outreach) |
| Calibrated confidence | ✅ | Temperature T = 2.722, ECE 0.218 → 0.089 (`decision.py`) | Note: max calibrated confidence is about 0.728, so "low uncertainty" is unreachable |
| Acoustic shadow evidence | 🟡 | `shadow.py`: paired flank asymmetry. Measured as **weak** (separation +0.13), so it is text only and never gates | A numeric shadow score (0–1) that fusion can use as *one* weak input |
| **Evidence Fusion engine** (all PDFs) | ❌ | `evidence_summary` = `{artificial_verification, shadow_context, notes}`, free-text strings | A structured **evidence vector** per target plus a transparent fusion rule that gives a verdict and reasons (§4.1) |
| "Three opinions": detector + anomaly + shadow agreement (PDF2 #6) | 🟡 | You already have **two independent models** for nets (YOLO box + U-Net mask) | Use agreement between YOLO and U-Net (and the quality/shadow scores) as an explicit fusion input |
| **CONFIRM / REVIEW / ABSTAIN** (all PDFs) | 🟡 | `review_only` flag, 3 uncertainty bands, suppression floors, `ReviewOnlyBanner.tsx` | A single explicit **verdict field** in the contract, the DB and the UI |
| "Unknown man-made anomaly" class (PDF1 #10, PDF2 #8, PDF4 #9) | 🟡 | Contract has `unknown`, and `normalise_class` falls back to `unknown` | Nothing *produces* `unknown` on purpose (for example, anomaly high + no confident known class) |
| **Sonar Anomaly Engine / "natural-first"** (PDF2 #1, #17) | ❌ | — | A seabed "normalness" model (see §4.6 for a cheap version) |
| Self-supervised / few-shot learning (PDF2 #2, PDF4 #3) | ❌ | — | Roadmap only. Not realistic before the finals on a 4 GB GPU. |
| Retrieval "similar sonar" search (PDF2 #7) | ❌ | — | Nice-to-have: embeddings from the YOLO backbone plus a cosine kNN over reviewed targets |
| "Why flagged?" sonar-specific explanation (PDF1 #5) | 🟡 | Evidence notes are prose | Generate the reason bullets **from the fusion vector** (✓ / ✗ list) |

### 2.3 Survey intelligence and GIS (the "ACT" layer)

| Idea | Status | Evidence | Missing |
|---|---|---|---|
| Geolocation with slant-range correction + `pyproj` | ✅ | `geo.py` | — |
| Location error circle | ✅ | `geo.position_error_m` (GPS + heading + altitude + layback, root-sum-square); map draws circles (`MapView.tsx`) | — |
| **Multi-frame tracking**: same target across frames/tiles (PDF1 #3, PDF2 #4, PDF4 #7) | ❌ | Each tile detection is a separate row | Associate detections in **ground coordinates**, giving a `Target` entity (§4.3) |
| **Multi-frame geolocation fusion** (PDF1 #9, PDF2 #5, PDF4 #8) | ❌ | — | Inverse-variance weighted mean of observations, giving a fused position plus a smaller 95 % radius |
| Vessel track on map | ✅ | `frame_position`, `map_service.get_survey_track` | — |
| Survey replay | ✅ | Map "▶ Replay" time playback (`app/app/map/page.tsx`) | **Evidence replay** per target (frames 101…106 of one target, synced to the map) |
| Coverage / blind-spot map (PDF1 #18, PDF2 #11, PDF4 #15) | 🟡 | Swath `corridor` polygon + "Sonar coverage" legend | Colour coverage by **quality**: green good, yellow poor, grey no data, red target. Add a "% corridor with insufficient coverage" KPI |
| Re-scan recommendation (PDF4 #16) | ❌ | — | Poor-quality area near a suspected target gives a "Re-survey zone" polygon |
| Repeat-survey change detection (PDF1 #19, PDF2 #12, PDF4 #17) | ❌ | — | Once Targets exist: match targets across two surveys by distance, giving NEW / REMOVED / PERSISTENT |
| Explainable priority (PDF1 #21) | 🟡 | `detection_service._priority_for`: keyed on class + uncertainty band | Show the **reason** ("High: repeated in 8 frames, low location error, ghost_net class") |
| Recovery mission planner (PDF1 #20, PDF2 #13) | ❌ | — | Nearest-neighbour + 2-opt route over HIGH/CRITICAL targets on the map, labelled "planning heuristic" |

### 2.4 Human-in-the-loop, provenance and platform

| Idea | Status | Evidence | Missing |
|---|---|---|---|
| Review queue: accept / reject / unknown + note | ✅ | `ReviewStatus` enum, `DetectionReview`, `ReviewPanel.tsx`, reviewer taken from JWT | Structured **reject reason** (rock / ripple / ridge / artifact / …) |
| Audit trail | ✅ | `AuditLog`, migration 0004 | — |
| Provenance chain: file → model version → reviewer (PDF1 #25) | ✅ | `model_version` on every detection, calibration-weights hash check, reports stamped | Show it as a "chain" block in the dossier |
| **Human corrections → hard-example store → retraining** (PDF1 #11–12, #23) | 🟡 | Hard-negative training exists on the *AI side* (`build_net_seg_hardneg.py`, gv9n, gvU1n) | **Nothing exports reviewed rejections from the app** into a dataset. Add a `/detections/export-training` endpoint plus a script (§4.5) |
| Active learning: "label these 50 first" (PDF2 #9, PDF4 #3) | 🟡 | `rank_label_suspects.py`, `mine_ghost_pot_candidates.py` exist offline | An "Uncertain first" sort in the review queue (by entropy, or by fusion conflict) |
| "What changed?" view: AI vs. human (PDF1 #23) | 🟡 | Review history endpoint | A small diff card: "AI: ghost_net 0.61 → Human: rejected (sand ridge) → stored as hard negative" |
| Reports | ✅ | CSV (BOM) + JSON/GeoJSON | **PDF target passport / mission report.** Judges love a printable artifact. |
| Offline / edge mode (PDF1 #24) | ✅ (implicitly) | Runs fully local (native Postgres, in-process AI) | Say it explicitly in the demo ("pull the network cable"). Sync is roadmap. |
| RBAC, rate limit, JWT | ✅ | migration 0004 | — |
| Robustness benchmark (PDF4 #12) | 🟡 | `evaluate_background.py` (7.82 % false alarms), `recall_by_size.py`, `evaluate_net_negatives.py`, `evaluate_sliced.py` | One **Robustness Report** that combines them, plus noise / low-contrast / long-range stress tests (§4.7) |
| **SonarOps Agent** (PDF3, PDF2 #14–15, PDF4 #13–14) | ❌ | No LLM or agent code anywhere | Everything in §4.4 |

### 2.5 Known open bugs to fix before any demo (from `docs/KNOWN_ISSUES.md`)

| ID | Issue | Why it matters for judging |
|---|---|---|
| **B3** | "Report for this detection" contains the whole survey | A judge clicks it and sees the wrong thing. This becomes critical once there is a Passport. |
| **B4** | Filtered report comes back unfiltered | Breaks the agent's "filter, then report" story |
| **B5** | Filter doesn't change map bounds | Visual polish |
| **C1** | `POST /reports` returns 500 on an unknown survey | A 500 shown on screen in a demo is fatal |
| — | Docker runs `MockAIAdapter` | Rule: **never demo from Docker.** Use the native path in `docs/DEMO_RUNBOOK.md`. |

---

## 3. Honest weaknesses judges WILL probe (prepare answers)

1. **"Your ghost_net box recall is 0.000?"** Answer: *"Yes, and that is why we reformulated nets as segmentation. The U-Net gets centroid detection 0.807 on held-out chips, and nets stay review-only until we have ≥300 real instances from ≥3 sites."* That is a strong answer. Keep it.
2. **"Only 11 test chips?"** Answer: small-sample caveat, 3 seeds with ± spread reported, and outreach to GhostNetZero (WWF / Microsoft) for more data.
3. **"Where did the 73 net chips come from?"** The README already discloses an open provenance question. Keep the disclosure; don't hide it.
4. **"Max confidence 0.728: is the model weak?"** Answer: calibration made it *honest*, not weak. Raw scores were overconfident (ECE 0.218 → 0.089). This is exactly why we need **evidence fusion** on top of confidence, which is the new module.
5. **"Debris mAP 0.869 comes from one survey?"** Say so before they ask.
6. **"Isn't this just YOLO + dashboard?"** This is the question the new modules (fusion, tracking, agent) exist to answer.

---

## 4. What to build next: prioritized, with concrete implementation plans

Effort assumes the 2 coding members. **P0 = must have for the win · P1 = strong differentiator · P2 = only if time.**

### 4.1 [P0] Evidence Fusion + CONFIRM / REVIEW / ABSTAIN gate (~2–3 days, Member 1 + contract bump)

**Where:** new `ai/ghostnet/fusion.py`, called at the end of `infer.detect_batch` and again at target level after tracking.

**Evidence vector per detection** (all numbers 0–1, each with a reason string):

| Signal | Source (already exists) | Notes |
|---|---|---|
| `model` | calibrated confidence | — |
| `shadow` | turn `shadow.py` flank asymmetry into a score | Weight it **low**; it measured weak |
| `data_quality` | `dropout.py` overlap + new quality score (§4.2) | — |
| `edge / geometry` | `decision.is_edge_sliver`, box aspect | — |
| `model_agreement` | YOLO box vs. U-Net mask overlap (for nets) | "Two opinions" |
| `persistence` | number of frames/tiles in the track (§4.3) | Target level only |
| `location` | fused `position_error_m` | Target level only |

**Gate (transparent rules, not a black box):**

```
ABSTAIN  if data_quality == POOR  or  (model < floor_q  and persistence <= 1)
REVIEW   if class in REVIEW_ONLY_CLASSES
         or signals conflict (e.g. model high but shadow/quality low)
         or location unavailable
CONFIRM  if model >= band_medium  and persistence >= N  and data_quality == GOOD
         and no conflicting signal
```

Tune `N` and the floors on the **validation split**. Don't invent numbers; PDF 1 says the same. Because the max calibrated confidence is about 0.73, CONFIRM will be rare, and that is honest and on-message.

**Contract:** add `verdict: "confirm"|"review"|"abstain"`, `evidence: {signal: {score, reason}}`, and `reasons_for: [...]`, `reasons_against: [...]` to `Detection` in `ai/ghostnet/contract.py`. Bump `CONTRACT_VERSION` to 1.3.0 and re-run `export_schemas.py`. Backend: migration `0006` adds a `verdict` column, and the existing `evidence_summary` JSON takes the rest.

**UI:** a verdict badge in `Badges.tsx`, a filter chip in `FilterBar.tsx`, and a ✓/✗ "Why flagged / Why uncertain" list in the detail page, replacing the raw key/value rows in `EvidenceSummary.tsx`.

**Tests:** extend `ai/tests/test_decision.py` with a table-driven test per gate rule.

### 4.2 [P0] Sonar Health Gate (~1 day, Member 1)

**Where:** new `ai/ghostnet/quality.py`, called once per frame in `survey.detect_survey`.

- **Noise / speckle:** coefficient of variation in homogeneous patches, or a median-absolute-deviation of the Laplacian
- **Contrast:** p95 − p5 intensity
- **Dropout %:** already available from `invalid_row_mask`
- **Nav availability:** already known (`has_geometry`)
- Output: `{score, label: GOOD|MODERATE|POOR, components}` on `FrameResult`. Store it in `SonarFrame.quality_status` (the column already exists and currently only holds `"ok"`).
- **Behaviour change** (this is what makes it a *gate*, not a chart): POOR → every detection goes to at least REVIEW (or ABSTAIN), and the per-class floor is raised.
- Calibrate the GOOD/MODERATE/POOR cut points on the test corpus distribution, and write down how in the docstring, the way `shadow.py` does.

**UI:** a per-segment health strip on the survey page, and the swath colour on the map (§4.6).

### 4.3 [P0] Track-to-Map Fusion: detections become Targets (~2–3 days, Member 1 algorithm + Member 2 DB/UI)

This is the **single biggest upgrade**. It fixes a known correctness issue (tile-seam duplicates), and it changes "image intelligence" into "survey intelligence".

**Algorithm** (new `ai/ghostnet/tracking.py`, run after `detect_survey` has all frames):

1. Put every geolocated detection in a local ENU/UTM metric frame (via `pyproj`).
2. Build a graph: link two detections if their distance is less than `k × sqrt(err_a² + err_b²)` (for example k = 2), their class is compatible, and they are close in frame/ping order.
3. Connected components = **Targets**. (Simple, explainable, no Kalman filter needed.)
4. **Fused position** = inverse-variance weighted mean. Fused error = `1/sqrt(Σ 1/σᵢ²)`, floored at the GPS error, because GPS bias doesn't average out. **Say this in the UI.** It is exactly the kind of honesty judges reward.
5. Target class = weighted vote. Target confidence = max or mean. Persistence = number of observations. Best view = the observation with the highest score.
6. Detections without geometry: associate in pixel space only, within the same ping block.

**Backend:** new `Target` model plus migration (`id, survey_id, class, verdict, fused_lat/lon, fused_error_m, n_observations, best_detection_id, priority`), and `Detection.target_id`. Endpoints: `GET /surveys/{id}/targets`, `GET /targets/{id}`.

**UI:** the map shows **targets** by default (with a toggle for raw detections). Headline KPI: **"47 detections → 19 unique targets"**, the exact line from PDF 3.

**Evaluation (important for credibility):** on the NBP0505 demo and the multi-frame fixtures, report the duplicate rate before and after. Don't claim location-accuracy gains without ground truth. Claim "radius shrinks with independent observations, bounded by GPS bias".

### 4.4 [P0] SonarOps Agent (~3–4 days, Member 2 + 1 pitch member to script the demo)

**Architecture (PDF 3's recommendation, and the right one):** the agent calls **your own FastAPI endpoints as tools**. It never drives the browser for the real work. The browser only *shows* what happened.

```
Operator prompt ──> Agent (LLM with tool-use) ──> Tool layer (thin wrappers) ──> existing /api/v1/*
                                   │                                                   │
                                   └─── streams plan/steps over existing WebSocket ◀───┘
```

**Tools**, mapped to routes that already exist in `app/backend/app/api/v1/`:

| Tool | Existing route |
|---|---|
| `create_survey`, `upload_file` | `POST /surveys`, `POST /surveys/{id}/files` |
| `inspect_metadata` | file validation result (`FileValidationCard` data) |
| `assess_sonar_quality` | new (from §4.2) |
| `start_processing`, `get_job_status` | `POST /surveys/{id}/process`, `GET /jobs/{id}` |
| `list_targets` / `filter_targets` | `GET /detections?…`, new `/targets` |
| `explain_target` | `GET /detections/{id}` (reads the fusion reasons) |
| `request_human_review` | adds to the review queue / Agent Inbox |
| `generate_report` | `POST /reports` (fix **B4** first so filters work) |

**Must-have agent features for the demo:**
- **Mission plan card** shown before execution, with checkmarks ticking live over the WebSocket.
- **Graceful agentic degradation:** GPS missing → *"I can still run detection, but geolocation will be unavailable. Continue?"* with [Continue] [Cancel]. The pipeline already returns `warnings[]` instead of errors, so the agent only has to read them.
- **Permission levels:** auto (upload, process, filter, draft report) vs. approval required (delete, finalize report, mark confirmed). This reuses the existing RBAC.
- **Agent Inbox:** "2 critical · 4 need review · 11 auto-confirmed · 3 unknown", built directly from the verdicts in §4.1.
- **Ask the agent:** "Why wasn't Target 24 confirmed?" The answer is generated from the fusion `reasons_against`. It is grounded, not hallucinated.

**Implementation:** new `app/backend/app/services/agent_service.py` and `api/v1/agent.py`, plus a chat panel component on the frontend. Use the Claude API with tool use (for example `claude-sonnet-5` for quality, or `claude-haiku-4-5` for speed and cost). Keep the API key server-side.

**Offline fallback (important for the "edge mode" claim and for flaky venue Wi-Fi):** a **deterministic mission runner** that executes the same tool sequence without the LLM when no internet is available. The demo never dies, and you can say "the LLM is a natural-language front end; the workflow itself runs offline."

**Optional wow:** add `data-agent-action="upload-sonar"` (and similar) attributes to key buttons. That makes a browser-agent replay possible later, but the API path is what counts.

### 4.5 [P1] Human learning loop, closed for real (~1 day)

- Add a structured `reject_reason` enum to the review (`rock`, `sand_ripple`, `ridge`, `sonar_artifact`, `water_column`, `other`), and render it as quick buttons in `ReviewPanel.tsx`.
- New endpoint `GET /detections/export-training?status=rejected_natural`. It returns tile + bbox/mask + reason as a YOLO/labelme zip that `ai/scripts/import_yolo.py` / `labelme_to_yoloseg.py` already understand.
- Show a "Hard-Example Bank: 37 examples (rock 14, ripple 11 …)" counter on the dashboard.
- **Do not** claim automatic improvement. PDF 4 warns about this. Claim "controlled retraining with validation gates", which you already do (`promote_net_model.py`).

### 4.6 [P1] Coverage Intelligence + Re-scan zones (~1–1.5 days, mostly Member 2)

- Split the existing swath `corridor` polygon into per-frame segments, coloured by the §4.2 label: **green GOOD, yellow MODERATE/POOR, grey no nav/no data**. Targets are red.
- KPI: **"18 % of the corridor has insufficient-quality coverage."** (compute this, don't hardcode it)
- **Re-scan zone** = POOR segment ∩ (a REVIEW/ABSTAIN target within X m, or a gap in coverage). Draw it as a hatched polygon with a reason tooltip.
- This answers "no detection ≠ no debris", which is one of the most mature points in all 4 PDFs, and it is cheap.

### 4.7 [P1] Robustness Report (~1 day, Member 1)

Combine the existing evaluation scripts into one `ai/scripts/robustness_report.py` that writes a single table:

| Condition | How |
|---|---|
| Clean test | existing `evaluate.py` |
| Hard negatives / empty seabed false alarms | `evaluate_background.py` (7.82 %), `evaluate_net_negatives.py` |
| Small objects | `recall_by_size.py` |
| + Gaussian / speckle noise σ = 1, 2, 3 | new augmentation at eval time |
| Low contrast (gamma, contrast × 0.5) | new |
| Far range only (tiles far from nadir) | filter by column distance |
| Unseen site (leave one source out) | the dataset split is already group-based |

Pitch line from PDF 4: **"We don't only test whether the detector works. We test when it stops being trustworthy."** Tie it to the gate: *the Health Gate thresholds come from this report.*

### 4.8 [P1] Target Passport (PDF export) + Evidence Replay (~1.5 days, Member 2)

- `/targets/{id}` page: sonar crop with mask and shadow side highlighted, verdict, ✓/✗ reasons, fused location plus radius, observation strip (all frames of the target, clickable and synced to the map, which *is* the "evidence replay"), provenance chain (file → model version + weights hash → reviewer → status).
- "Export Passport (PDF)" using a server-side HTML-to-PDF step (for example WeasyPrint), or `window.print()` with a print stylesheet as the zero-dependency route. This also properly fixes bug **B3**.

### 4.9 [P2] Only if time remains

| Feature | Cheapest credible version | Effort |
|---|---|---|
| Recovery mission planner | Nearest-neighbour + 2-opt over HIGH/CRITICAL targets, polyline on the map, labelled "planning heuristic" | 0.5 day |
| Repeat-survey change detection | Match Targets across 2 surveys (distance less than the combined radius): NEW / REMOVED / PERSISTENT. Demo with the same file processed twice, plus one survey with frames cut | 1 day |
| Cheap Anomaly Engine ("natural-first") | Per-tile local-texture statistics (GLCM / LBP histograms) vs. a survey-wide median, giving an anomaly heat map. Use it as a fusion input and to produce `unknown` when anomaly is high but no known class is confident | 1.5–2 days |
| Similar-sonar retrieval | Pool YOLO backbone features per crop, cosine kNN over reviewed targets, show the "3 most similar reviewed examples" in the Passport | 1 day |
| Domain fingerprint | Per-survey intensity-histogram + speckle stats vs. the training distribution (KL or Wasserstein distance), shown as a "Domain match: LOW/MED/HIGH" input to fusion | 1 day |
| Range-aware thresholds | Floor as a function of distance from nadir, fit on validation | 0.5 day |

**Don't build before the finals:** self-supervised pretraining, full domain adaptation training, a Kalman tracker, sync-to-central-DB, or a browser-automation agent as the main path. Put them on a "Roadmap" slide.

---

## 5. Suggested build order (about 10 working days)

| Day | Member 1 (AI) | Member 2 (App) | Members 3–4 (Pitch) |
|---|---|---|---|
| 1 | `quality.py` Health Gate + tests | Fix **B3, B4, C1** (and B5 if trivial) | Rewrite PPT story to SEE → TRUST → ACT |
| 2–3 | `fusion.py` + gate + contract 1.3.0 | Migration 0006 (verdict), badges, filter, "Why flagged" list | Script the demo (see §6) |
| 4–5 | `tracking.py` + fused geolocation + duplicate-rate measurement | `Target` model/API, map shows targets, "47 → 19" KPI | Judge Q&A sheet (§3) |
| 6–7 | Robustness report | Agent service + tools + mission-plan card + inbox | Record a backup demo video |
| 8 | Hard-example export format | Reject reasons + export endpoint + coverage colouring + re-scan zones | Architecture diagram slide |
| 9 | Freeze the model and re-run all evidence numbers | Target Passport page + PDF export | Rehearse with a timer |
| 10 | **Feature freeze.** Full dry runs, native (not Docker) | Offline fallback for the agent, tested with Wi-Fi off | Final PPT numbers checked against `MODEL_CAPABILITY_EVIDENCE.md` |

---

## 6. The demo script (5 minutes, built around the new modules)

1. **(20 s) Problem:** ghost nets keep fishing for years, and side-scan sonar is noisy.
2. **(60 s) SonarOps Agent:** type *"Process NBP0505, find likely man-made targets, ask me only when something needs review, and prepare the report."* The mission plan appears and the checkmarks tick live over the WebSocket.
3. **(30 s) Graceful degradation:** upload a file without nav. The agent asks *"GPS missing, continue with image-space detection?"*
4. **(45 s) Survey intelligence:** the map shows a coverage swath (green/yellow/grey), **"47 detections → 19 targets"**, fused error circles, and a re-scan zone.
5. **(60 s) Target Passport:** click a target to see the evidence replay across frames, ✓/✗ reasons, verdict REVIEW, and "Why not confirmed?" answered by the agent from real evidence.
6. **(30 s) Human loop:** reject as "sand ripple". The "What changed" card appears and the Hard-Example Bank goes +1.
7. **(30 s) Trust:** Robustness Report slide and the honest ghost_net story (box 0.000 → U-Net centroid 0.807, still review-only).
8. **(15 s) Close:** *"Not just a sonar object detector: it converts uncertain acoustic observations into verified, geolocated, actionable marine intelligence."*

**Backup:** a pre-recorded video of the same flow, plus the offline deterministic runner if the LLM API is unreachable.

---

## 7. Pitch / PPT changes (for the `GhostNet-AI_SIH26057_Official_Template.pptx`)

- **Replace** "YOLO11-S + FastAPI + GIS" as the headline with **SEE → TRUST → ACT** (PDF 2), or **Adapt → Detect → Verify → Abstain → Localize → Act** (PDF 4).
- **Center slide:** "Model confidence ≠ operational trust", with a side-by-side example: 91 % confidence + poor quality + weak shadow + seen once gives **REVIEW**.
- **Innovation slide:** the 5 modules, each with a screenshot from the working app. Judges trust screenshots more than diagrams.
- **Evidence slide:** real numbers only, all taken from `docs/MODEL_CAPABILITY_EVIDENCE.md`. Label every number *measured on held-out data* or *illustrative*.
- **Negative-results slide:** gv6 synthetic (0.000), TTA (−4 pp recall), box → segmentation. This shows research maturity.
- **Avoid:** "first in the world", "99 % accuracy", "autonomous recovery", and synthetic numbers presented as field numbers.
- **Differentiation line (PDF 1):** *"Our advantage is the combination and the working implementation: sonar-aware processing + evidence fusion + abstention + multi-frame geolocation + human review + agent-orchestrated GIS workflow."*

---

## 8. One-page summary for the team

| Category | Count | Items |
|---|---|---|
| ✅ Already done | ~20 | XTF ingest, geometry from headers, port/starboard fix, dropout, calibration, asymmetric floors, review-only nets, U-Net net segmentation, shadow evidence (text), slant-range geolocation, error circles, track + replay, review queue + audit, RBAC, provenance/model version, CSV/GeoJSON reports, leakage-safe splits, hard-negative training, offline native run, honest negative results |
| 🟡 Partial: finish these | ~12 | Evidence fusion, 3-state gate, sonar health gate, coverage map, adaptive thresholds, unknown class, explainable priority, "why flagged", hard-example loop from the app, active learning in the UI, robustness report, dossier/passport |
| ❌ Missing: build the P0s | 5 P0 | **Evidence Fusion + Gate**, **Health Gate**, **Track-to-Map Fusion**, **SonarOps Agent**, (plus the P1 Passport, Coverage/Re-scan, Robustness, Learning loop) |
| 📌 Roadmap slide only | — | Self-supervised learning, domain adaptation training, change detection (unless time), anomaly engine (unless time), retrieval search, mission planner (unless time), central sync |

**If you only have 5 days:** Health Gate → Fusion + Gate → Tracking/Targets → Agent (with offline fallback) → fix B3/B4/C1. That alone moves GhostNet-AI from "a good detector with honest numbers" to "a trustworthy sonar intelligence system", which is the story all four PDFs are asking for.
