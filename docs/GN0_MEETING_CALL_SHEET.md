# Call sheet — GhostNetZero / WWF, after 17 September 2026

Open this on a second screen during the call. You are reading, not
remembering. Nothing here needs to be memorised.

**Who is on the call**
- **Gabriele Dederer** — WWF Germany. Ghost-net lead, co-first-author. The
  conservation and permissions side. Wrote the reply.
- **Zhongqi Miao** — Microsoft AI for Good Lab, co-first-author. The technical
  half. Any modelling question will come from here.
- **Mareen Lee** — WWF Germany, co-author on the report.
- **Luana** — WWF, not on the paper.
- Possibly **Juan Lavista Ferres** — head of the AI for Good Lab, cc'd.

**Open with this, then stop talking**
> "Thanks for making time. Would you like me to walk through what we did, or
> would you rather just ask questions?"

---

## The four questions you will actually be asked

**1. Who are you?**
A student team building a five-class side-scan sonar detector for Smart India
Hackathon problem SIH26057. Classes: ghost_pot, debris, wreck, natural,
ghost_net. Say "student project" plainly — it is why they would help, not a
reason they would not.

**2. What data do you have?**
- 73 hand-annotated real net chips, two Chinese coastal sites (quanzhou,
  yantai). Small pre-cut chips, roughly 350-740 px on a side, not tiles of a
  waterfall.
- Re-annotated by us as **425 polygons**, one per bead chain.
- Split 51 train / 11 val / 11 test, inherited from the earlier detection
  dataset by filename so nothing leaks.
- Plus the wider five-class set: ~6,600 GhostVision crab-pot frames
  (CC-BY-SA 4.0), SubPipe pipelines (CC BY 4.0), and others.
- **If asked where the net chips came from: "I need to check our provenance
  records and come back to you."** Do not guess. This is genuinely unresolved
  on our side and it is the honest answer.

**3. What did you do?**
Changed one variable — label geometry and task head. Same 73 images, same
split, same sensor.
- Before: bounding boxes, YOLO11-S → `ghost_net` **recall 0.000** across six
  training generations. The model never emitted a single net prediction.
- After: polygons, YOLO11-S-seg → **recall 0.525** on test.
- Mechanism: median frame area labelled "net" fell from **56.5% to 7.0%**.
  Under boxes, most pixels labelled net were empty seabed, so the class's
  dominant training signal was background. It learned to predict nothing, and
  it learned that correctly.
- 608 epochs, ~56 minutes, 4 GB consumer GPU. An identical 300-epoch run only
  reached Mask mAP50 0.059 — on 51 images it had not converged.

**4. What do you want?**
- The labelled BS / PS segments, **for evaluation rather than training**. With
  11 test chips we can only state true recall is below 8.3%, so we cannot tell
  a real improvement from noise.
- Sonar over the MARELITT Baltic fleets off Simrishamn, if it is shareable.

---

## The six numbers, if you need them fast

| | |
|---|---|
| Test, 11 chips / 59 inst | Box P 0.485 · **R 0.525** · mAP50 0.473 |
| | Mask P 0.318 · R 0.390 · mAP50 0.204 |
| Val, 11 chips / 44 inst | Box P 0.501 · R 0.727 · mAP50 0.653 |
| Box formulation, same class | P 0.000 · R 0.000 · mAP50 0.005 |
| Area labelled net | 56.5% (boxes) → 7.0% (polygons) |
| Their model, for reference | mIoU 0.739 BS / 0.685 PS · CD 0.891 / 0.929 |

## Three things not to say

1. Never **"in collaboration with Microsoft."** You are in correspondence with
   two authors. That is already good.
2. Never quote **0.525 beside a box-model mAP50** — different task, different
   label geometry, different metric. If someone else does it, correct them.
3. Never call the class **working**. It ships review-only: a net prediction
   enters a human queue and is rendered differently from a confirmed hit. Our
   promotion rule for quoting it without caveat is ≥300 real instances from
   ≥3 sites, recall ≥0.30, three seeds, non-overlapping bootstrap CI.

## Two answers that are always available

- **"I'd rather not guess — let me check and email you."** Strong, not weak.
  Their own study has no test set; they know provisional work.
- **"Let me confirm on our side and write to you."** Use this for anything
  about data sharing, licensing or upload. Agree to nothing live.

## Questions worth asking them

- How are contributed regional datasets credited, on the platform and in
  future publications?
- Is the trained model's inference on GN0 available for imagery we upload, or
  is upload donation-only?
- Their BS-only model scored 0.607 on PS — how do they expect cross-region
  transfer to behave on a third region?
- Are they moving to instance rather than semantic segmentation, given they
  count several polygons over one net as a single true positive?
- Is there a path to the Puget Sound owners — Fenn Enterprises, Northwest
  Straits Foundation, Natural Resources Consultants?

**If it lasts 20 minutes and ends with "let's follow up by email," that was a
success.** A first call is scoping, not delivery.
