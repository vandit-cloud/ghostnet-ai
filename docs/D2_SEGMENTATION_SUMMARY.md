# Ghost nets in side-scan sonar: box formulation vs segmentation

**An independent reproduction of GhostNetZero's task-formulation finding on
Chinese coastal side-scan imagery.**

GhostNet-AI · Smart India Hackathon problem SIH26057 · 13 September 2026
Contact: Vandit Doshi

---

## Context

We are a student team building a five-class side-scan sonar detector for marine
debris and derelict fishing gear: `ghost_pot`, `debris`, `wreck`, `natural`,
`ghost_net`. Four classes train acceptably. The net class did not train at all.

Across six training generations, `ghost_net` scored **recall 0.000** — the model
never emitted a single net prediction on the test split. Our working assumption
was insufficient data.

The GhostNetZero technical report (Microsoft AI for Good Lab, WWF Germany,
Accenture, September 2025) contradicted that assumption. It reports ~90%
centroid detection from **412 real annotated segments** — 239 Baltic Sea, 173
Puget Sound. That is a small dataset succeeding where ours failed, which
relocates the diagnosis from data volume to task formulation. The report states
the reason directly: segmentation gives "more accurate localization...
particularly important for irregularly shaped ghost nets, such as those in
string-like shapes."

We tested that claim on our own data.

## What we changed

One variable: **label geometry and task head.** Same 73 images, same
train/validation/test split, same sensor, same sites.

| | Before | After |
|---|---|---|
| task | bounding-box detection, YOLO11-S | instance segmentation, YOLO11-S-seg |
| labels | 73 hand-drawn boxes | **425 polygons** over the same 73 chips |
| classes | 5 | 1 (`ghost_net` only) |
| split | 51 / 11 / 11 | 51 / 11 / 11, inherited unchanged |

The polygon convention: one polygon per bead chain, running down the middle of
the strip, roughly 6-7% of the chip's short side in width, vertex count
following the chain's actual bends, stopping where the beads stop.

Rotation augmentation was disabled deliberately — in side-scan, across-track
is range, so a rotated tile is not an image the sonar can produce and shadows
fall wrong. Horizontal and vertical flips were kept: they correspond to a
port/starboard mirror and to the vessel running the reciprocal track.

## Result

**Test split, 11 chips / 59 instances. Three seeds, reported as mean ± sd:**

| metric | before (box model) | after (segmentation) |
|---|---|---|
| **Box recall** | **0.000** | **0.492 ± 0.074** |
| Box precision | 1.000 (on zero predictions) | 0.663 ± 0.050 |
| Box mAP50 | 0.009 | 0.528 ± 0.018 |
| Mask mAP50 | — | 0.227 ± 0.012 |
| **Centroid detection rate** | **0.000** | **0.607 ± 0.031** |
| Centroid precision | — | 0.496 ± 0.042 |

Per seed, box recall was 0.576 / 0.458 / 0.441 and the centroid detection rate
0.600 / 0.640 / 0.580. Training was 1000 epochs, ~75 minutes per seed on a 4 GB
consumer GPU.

**Which figure to read.** Recall carries much the widest variance, because it
steps coarsely over 59 instances — one instance found or lost moves it ~0.017.
Box mAP50 (sd 0.018), mask mAP50 (0.012) and the centroid rate (0.031) are all
substantially more stable. We adopted the centroid detection rate for
operational reasons, described below, and it turned out to be the
better-behaved measurement as well; it was not selected because it flattered
the result.

**An earlier version of this document quoted box recall 0.525 from a single
seed.** That figure was one draw reported without a spread and slightly
optimistic against the mean; it lies inside the range above. The correction is
described in "What replication cost us", below, because how we found it matters
more than the revision itself.

## The likely mechanism

Median frame area claimed as `ghost_net` fell from **56.5% under hand-drawn
boxes to 7.0% under polygons** — an eightfold reduction in seabed labelled as
net.

A net in side-scan is a long, thin, diagonal chain of floatline beads. Its
axis-aligned bounding box is mostly water. Under the box formulation, the
majority of the pixels the model was shown as "ghost_net" were empty seabed —
so the class's dominant training signal was seabed, which is also the dominant
background. The class was being taught to predict nothing, and it learned that
correctly.

Separately, we tested despeckle filtering at training time as a competing
hypothesis. It was a clear negative for nets under the box formulation
(`ghost_net` P 0.000, R 0.000, mAP50 0.005), consistent with GhostNetZero
reaching ~90% with no despeckling at all.

## Measuring a fragmented target

We have adopted your centroid detection rate alongside mAP50, and we think the
argument behind it is correct: three disconnected polygons over one continuous
net should count as one true positive, not one hit and two false alarms. For a
target whose annotation seams are arbitrary, IoU penalises the model for a
fragmentation that has no operational consequence.

Implementing it forced a decision we would rather state than leave implicit.
**Both ground truth and predictions are clustered into *nets* before matching** —
single-linkage on centroid distance at the match tolerance — and net centroids
are then matched one-to-one, nearest pair first. Single linkage chains, which is
usually its flaw and here is the point: a long net traced as several bead chains
end to end has distant endpoints and is still one net.

We rejected two alternatives. Strict one-to-one matching on polygons
reintroduces the fragmentation penalty the metric exists to remove. Lenient
many-to-one cannot charge for over-prediction at all, and since our predictions
feed a human review queue, that cost is real and must remain countable. The
price of our choice is that the denominator is nets (50) rather than polygons
(59), so these figures do not sit on the same footing as mAP50.

**The rate is strongly tolerance-dependent, so we publish the sweep rather than
a point:**

| tolerance (chip widths) | GT nets | detection rate | precision |
|---|---|---|---|
| 0.05 | 59 | 0.508 | 0.462 |
| 0.08 | 53 | 0.623 | 0.532 |
| **0.10** | **50** | **0.680** | **0.567** |
| 0.15 | 32 | 0.656 | 0.512 |
| 0.20 | 23 | 0.739 | 0.515 |
| 0.25 | 16 | 0.812 | 0.565 |
| 0.30 | 15 | 0.800 | 0.571 |

(Single seed, for comparability with the sweep as first computed; the
three-seed figure at tolerance 0.10 is 0.607 ± 0.031.)

Two cautions we would apply to anyone else's centroid numbers, including our
own. The headline is dialable — quoting 0.812 by selecting tolerance 0.25 would
be indefensible, since a quarter of a chip width is not "pointing at the spot"
and the denominator has collapsed to 16. And the rate is **not monotonic** in
tolerance, which is the sample size talking rather than the model.

We fixed one defect worth passing on. YOLO normalises x by image width and y by
image height *independently*; that is harmless for boxes and wrong for
distances. Our chips range from 322×280 to 331×112, so on the 3:1 chip a
"distance of 0.10" was 33 px across and 11 px down — the match tolerance was an
ellipse of a different shape on every chip, and in side-scan the two axes are
not interchangeable, since across-track is range and along-track is vessel
travel. Correcting it moved the headline from 0.596 to 0.680.

**We have no physical grounding for the tolerance.** These chips come from
published figures with no recorded ground resolution, so it cannot be stated in
metres. Given georeferenced data it should be re-derived from a diver search
radius, which is the quantity that actually matters.

## What replication cost us

We ran the experiment three times with different random seeds, per our own rule
that no result is quotable on one run. It did not produce an error bar. It
produced a bug.

Under our original early-stopping setting, one seed scored mask mAP50 **0.004**
against the others' 0.204 and 0.153 — apparent catastrophic seed variance. It
was not. That run stopped at **131 epochs** where the others ran 608 and 558.

On 51 training images this model sits at mask mAP50 ≈ 0.000–0.002 for roughly
the first 200 epochs **in every seed** before it learns anything at all. That
flat region is structural, not a plateau of convergence. Early stopping asks
"has it improved lately?" inside that region, where the metric is pinned near
zero and moves only in the fourth decimal — so the decision is made on noise.
Two seeds twitched upward often enough to survive it. One did not.

Worse, both surviving runs peaked at epochs 586/608 and 551/558 — still
improving when patience ended them. The setting was cutting *every* run short,
including the one our published figure came from.

With early stopping disabled, seed spread on mask mAP50 fell **0.101 → 0.012**,
and the seed that had looked catastrophic came back as the best of the three.

We pass this on because the failure is not specific to our data. **Early
stopping assumes the metric it watches is informative from the start, and on a
small dataset it is not, for hundreds of epochs.** Anyone reproducing this kind
of result on tens of images should treat patience as a parameter to justify
rather than inherit — and a single-run number can hide a training failure that
looks exactly like a modelling result.

## What we are not claiming

**Our test split is 11 chips from 2 sites. It cannot support a performance
claim, and three seeds do not change that.** The figures above are reported as
upper bounds and are not comparable with our box-model scores — different task,
different label geometry, different metric.

The distinction we are careful about: the seeds agree closely with each other,
which says the training procedure is stable. It says nothing about whether the
result transfers. **Seeds agreeing with each other is not sites agreeing with
each other**, and with two sites on one coastline, "the model learned nets" and
"the model learned Chinese coastal seabed" predict identical numbers on our test
split. Nothing we can run distinguishes them.

Your own Baltic-only model scoring 0.607 on Puget Sound is the reason we treat
that as a live concern rather than a formality.

In our own system the class ships under a review-only contract: a net
prediction never asserts a detection, it enters a human review queue and is
rendered differently from a confirmed hit.

Our promotion rule requires **≥300 real net instances from ≥3 sites, recall
≥0.30, three seeds with spread below the effect size, and a non-overlapping
bootstrap confidence interval**, under both mAP50 and centroid detection rate,
before the class may be quoted without that caveat. As of this writing three of
the five conditions are met; the outstanding one that matters is the first, and
**no training run can clear it** — it is a data requirement, which is why we are
writing.

## Why we are writing

The measurement problem now precedes the modelling problem. We have a
formulation that works and no way to prove how well, because 73 images from two
sites cannot both train and evaluate a model.

**What would change that:** access to the labelled Baltic Sea / Puget Sound
segments as an evaluation set, and sonar over the MARELITT Baltic ghost-net
fleets off Simrishamn, whose diver-verified ground truth is close to unique for
this problem. We note that GhostNetZero's own Baltic-only model scored 0.607 on
Puget Sound — cross-region transfer is weak, which is a caution we would apply
to our own two-site data as well.

**What we can contribute:** the 425 polygon annotations over these 73 chips,
the labelling convention, the dataset-build and training scripts, our
implementation of the centroid detection rate including the clustering rule and
the aspect-ratio correction described above, and our evaluation discipline for
very small n — including the early-stopping failure, which we would not have
found without seeding a result we already believed.

We adopted your centroid detection rate independently of this request and would
keep it either way: the argument that several disconnected polygons over one
long net should count as one true positive is correct, and IoU-based metrics
penalise us for a fragmentation that does not matter operationally.

---

*Reference: GhostNetZero: AI for Detecting Marine Ghost Nets, Microsoft AI for
Good Lab / WWF Germany / Accenture, technical report September 2025.*
