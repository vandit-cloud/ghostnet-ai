# Draft reply — Gabriele Dederer (WWF DE) / Zhongqi Miao (Microsoft), GN0 thread

Received 2026-09-08. Reply keeps the thread's recipients: Gabriele Dederer,
Zhongqi Miao, cc Juan Lavista, Luana, Mareen.

**Before sending, fill the two bracketed slots and resolve the upload question
(see `D2_SEGMENTATION_SUMMARY.md` and the licence note at the bottom).**

---

Subject: Re: [EXTERNAL] Replicating GhostNetZero's segmentation finding on
Chinese coastal SSS - a small dataset offer

Dear Gabriele,

Thank you — and no problem at all about the timing. After the 17th suits us
well.

Thirty minutes would be plenty to cover the essentials, and I am glad to stay
for longer if it is useful — please book whatever length suits you. Any of
these afternoons works, all times CEST:

- Friday 18 September, 12:00-17:00
- Monday 21 September, 12:00-17:00
- Tuesday 22 September, 12:00-17:00

We are in India (CEST + 3:30), so a European afternoon suits us well. Send an
invite for whatever slot is easiest for you and Zhongqi and we will be there.

If it is simpler for your team, I am equally happy to cover the substance in
writing first — I have set out our result and our two questions below, and can
answer follow-ups by email at whatever pace suits you around the application
deadline.

In the meantime, here is a summary of the result I mentioned, in case it is
useful background before we talk. The short version: on 73
hand-annotated side-scan chips from two Chinese coastal sites, the same net
class that trained to **recall 0.000** as bounding boxes reached **recall
0.525** once we re-annotated it as polygons and trained a segmentation head.
That is an independent reproduction of your central finding — that box
formulation is the wrong task for string-like nets — on a different sea, a
different sensor and a different annotator. The mechanism looks simple: our
median frame area labelled "net" fell from 56.5% to 7.0% when we moved from
boxes to polygons, so most of what the boxes taught the model was empty
seabed. We report it only as an upper-bound result; our test split is 11 chips,
which cannot support a performance claim.

Two things I would like to put on the agenda:

1. **Access to the labelled Baltic Sea / Puget Sound segments**, for evaluation
   rather than training. Our measurement problem is worse than our training
   problem: with 11 test chips we can only state that true recall is below
   8.3%, so we currently cannot tell a real improvement from noise. Even a
   held-out evaluation subset would change what we are able to conclude.
2. **The MARELITT Baltic ghost-net fleets off Simrishamn** — if sonar over
   those two 400 m deployments exists in a shareable form, a diver-ground-
   truthed testbed is uniquely valuable for exactly this problem.

On GN0: I registered, and the platform tells me my access is pending approval
by the GhostNetZero admins — so the account is not active on my side yet. No
urgency at all from us; it can wait until after the 17th along with everything
else. I mention it only because you may have expected it to be live already.

I have read the terms in the meantime, and I do not think I can upload our net
imagery in good conscience. I would rather explain why than go quiet on it.

The uploader warranty asks me to confirm that I hold all rights in the uploaded
data and that no third-party rights are infringed. Our 73 net chips are
third-party side-scan imagery whose origin we have not yet been able to
document, so that is a warranty I cannot honestly give — and the accompanying
indemnity should not rest on a warranty nobody can support. The rest of our
imagery is licensed CC BY or CC BY-SA, which means the onward, sublicensable
rights the terms ask for are not mine to grant either. I would rather tell you
this plainly than have it surface later.

What I can offer is the work that is genuinely ours, and I am happy to provide
it outside the upload flow under whatever licence you prefer: the 425 polygon
annotations over those 73 chips, the labelling convention we wrote for them,
our synthetic net imagery, and the dataset-build and training scripts. If it
would help, we are also glad to annotate imagery that you hold — the
convention and the tooling already exist, and the annotation bottleneck your
report describes in §4.3 is the part we are set up to help with.

I also could not find an attribution clause in the terms, so one practical
question for the meeting: how are contributed regional datasets credited, on
the platform and in any future publication? And in the other direction — the
terms reserve the Application's contents to WWF and require prior written
permission for derivative use, so if evaluation data were shared with us, we
would want that permission in writing rather than assumed.

Our code, annotations and labelling convention go public later this week as
part of a hackathon submission — I will send the repository link once it is
live, in case you or Zhongqi would like to look at the method directly.

Looking forward to speaking after the 17th.

Best regards,
Vandit Doshi
[team / institution line]
[phone or alternate contact, optional]

---

## Notes for us, not for sending

**Why the upload is hedged.** The 73 net chips
(`ai/data/annotate/ghost_net_seg/images/`, quanzhou_HN / yantai_HN) have no
recorded provenance or licence anywhere in the repo:
`ai/data/provenance/data_inventory.csv` has no row for them, the raw sources
were pruned in `ad70122`, and `docs/DATA.md` records that none of our sources
ship a formal licence file. Uploading imagery to a platform run by
Microsoft/WWF/Accenture is redistribution. Our polygons, scripts and derived
tiles are cleanly ours and can go up immediately; the underlying pixels cannot
until someone establishes where they came from.

**What NOT to say.** Do not quote the 0.525 next to gv5's mAP50 — different
task, different label geometry, different metric. Do not describe the class as
working; it is Tier 1 (review queue) under gv7 plan §10.5.

**If they ask what we can offer that is clearly ours:** GhostVision-derived
crab-pot tiles are CC-BY-SA 4.0 (attribution + share-alike, so the derived set
must carry the same licence), SubPipe is CC BY 4.0. Both are already public on
Zenodo, so they add little to GN0 — the genuinely novel contribution we hold is
the Chinese coastal net imagery, which is exactly the piece with the licence
question.

**What "you have access to the GN0 platform" means** (report §4.2 and Figure 3,
verified from the PDF 2026-09-08). GhostNetZero.ai is a *human-in-the-loop*
platform built with Accenture. Its pipeline is: **user uploads sonar → the
trained model generates preliminary predictions marking segments likely to
contain nets → a human expert validates them → the validated feedback feeds
model retraining.** So an account is not just a drop box: it is inference from
their BS+PS model (mIoU 0.739 BS / 0.685 PS, centroid detection 0.891/0.929)
plus a review UI.

Two consequences. (1) Anything we upload enters a **retraining loop** — it is a
contribution to their model, not a private evaluation, which raises the licence
question above from "redistribution" to "redistribution plus derived use".
(2) Running our 73 chips through their model would be a genuinely interesting
cross-region transfer test (their BS-only model scored 0.607 on Puget Sound, so
Chinese coastal water is a real test of generalisation) — but it is a *post-
hackathon* experiment, not a pre-12-September one.
