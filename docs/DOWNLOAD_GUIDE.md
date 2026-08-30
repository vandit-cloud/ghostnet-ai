# Download guide — do these in order

Plain steps for getting the sonar data onto your PC. Every link below was
checked on **2026-08-30**. File sizes are real, read from the GitHub API, not
guessed.

**Total hands-on time: about 40 minutes.** Most of that is waiting for downloads.

Run every command from the project root (`E:\New folder`) in **Git Bash** or
PowerShell.

---

## Before you start: folder names matter

The inventory tool matches your folder name against the dataset registry. Use
the **exact** names given in each step. Get it wrong and the tool reports
`provenance unrecorded` and cannot check the data against what was promised.

---

# STEP 1 — SCTD  ⏱️ 10 min  🟢 do this first

**The best dataset available to you.** Real side-scan sonar, real bounding
boxes, no account and no permission needed.

### Download

**Link:** <https://github.com/MingqiangNing/SCTD>

Click **`SCTD.zip`**, then the **Download** button. It is **79 MB**.

Or from the terminal:

```bash
curl -L -o "$TEMP/SCTD.zip" \
  https://github.com/MingqiangNing/SCTD/raw/master/SCTD.zip
```

> **Ignore `SCTD2.0.rar`.** It looks like a second dataset but it is only 134
> bytes — a placeholder pointer, not real data. Downloading it gets you nothing.

### Where to put it

Extract so the images end up inside this exact folder:

```
E:\New folder\ai\data\raw\research\SCTD\
```

### Check it worked

```bash
.venv/Scripts/python ai/scripts/inventory.py --verbose
```

**What good looks like:** a block headed `== SCTD` showing an image count,
pixel sizes, and `annotation_type: VOC XML boxes`.

**Expect a count warning.** The paper claims 596 images but the published class
breakdown adds up to 357. The tool will tell you which is actually true — that
is exactly what it is for. Whatever number it prints is the real one. Tell me
what it says.

---

# STEP 2 — Email for the KLSG seafloor images  ⏱️ 5 min  🔴 send today

**Send this before you do anything else that takes time.** Researchers reply in
days, not minutes. If you wait until you are blocked, you have lost a week.

### Why you have to email

Your build plan depends on **578 plain-seabed images** for "hard negatives" —
pictures of ordinary seafloor with nothing on them, which teach the model not to
cry wolf at every rock.

Those images are real, but **they are not published anywhere**. I checked:

| Where you would look | What is actually there |
|---|---|
| `huoguanying/SeabedObjects-Ship-and-Airplane-dataset` | 4 zips: ships and planes only. **No seafloor.** |
| `HHUCzCz/-SeabedObjects-KLSG--II` — *advertises the 578* | **One 45 KB sample photo. That is the whole repository.** |

Three open issues on that second repo ask for the full dataset. None have been
answered. So email is the only route, and it may not work.

**Do not let this block you.** Step 5 is the backup and it is fine.

### Who to email

`huoguanying@hhu.edu.cn` and `huoguanying@163.com` — send to **both**.

### Text you can paste

> **Subject:** Request for access to the complete SeabedObjects-KLSG dataset
>
> Dear Dr Huo,
>
> I am an undergraduate student working on an underwater marine-debris detection
> project for the Smart India Hackathon, using side-scan sonar imagery.
>
> I have downloaded the publicly released ship and airplane images from your
> GitHub repository, and they have been very useful. I am writing to ask whether
> the complete SeabedObjects-KLSG dataset is available for academic use —
> particularly the **578 seafloor images**, which I would like to use as
> negative examples so that the model learns to distinguish natural seabed from
> man-made objects.
>
> The work is academic and non-commercial, and I will cite your dataset and
> paper in full in any report I produce.
>
> Thank you for making this data available to the research community.
>
> Kind regards,
> [your name]
> [your college]

### While you wait

Take the ship and airplane images anyway — they are useful positives:

**Link:** <https://github.com/huoguanying/SeabedObjects-Ship-and-Airplane-dataset>

Download `plane-real.zip` (6 MB) and `ship-real-1.zip`, `ship-real-2.zip`,
`ship-real-3.zip` (~44 MB together). Extract all four into:

```
E:\New folder\ai\data\raw\research\KLSG\
```

---

# STEP 3 — Kaggle mirror of KLSG  ⏱️ 5 min  🟡 might save you the wait

Someone re-uploaded KLSG to Kaggle. **It may include the seafloor images the
GitHub repos are missing.** I could not check — Kaggle needs a login — so you
have to look.

**Link:** <https://www.kaggle.com/datasets/enochkwatehdongbo/seabedobjects-klsg-dataset>

### Just download it — the preview often will not load

Kaggle's file browser frequently fails to render for anonymous or new accounts.
**Do not let that stop you.** Download blind:

- **Cost if it is the wrong thing:** ten minutes and a few hundred MB.
- **Payoff if it is the right thing:** the email in Step 2 stops mattering, and
  your hard-negative problem is solved today.

That trade is not close.

Weak but real evidence it is the full set: this mirror is titled
`SeabedObjects-KLSG_Dataset`, not "Ship-and-Airplane" like the partial GitHub
repo, and its description lists the seafloor sub-types (rock, mud, sand, sand
waves, sand ridges, clay) — detail that only appears in the full dataset.

1. Sign in to Kaggle (free) and hit **Download**.
2. Extract to `E:\New folder\ai\data\raw\research\KLSG-KAGGLE\`
3. Check what you actually got:

```bash
.venv/Scripts/python ai/scripts/inventory.py --verbose
```

Look at the **`classes`** line in the `== KLSG-KAGGLE` block. It counts images
per folder, so it tells you immediately whether a seafloor class is present.

- **`seafloor:578`** or similar → you are done, and Step 5 becomes optional.
- **only ship / plane** → it is the subset you already have. Delete it and rely
  on Step 2 or Step 5.

Tell me the `classes` line either way — it decides whether Step 5 is optional
or essential.

---

# STEP 4 — AI4Shipwrecks  ⏱️ 15 min  🟢 worth having

286 high-quality side-scan images of 28 shipwrecks, with **exact outlines drawn
around each wreck** (not just boxes). The most precise labels available to you.

**Link:** <https://umfieldrobotics.github.io/ai4shipwrecks/>

Follow the download link on that page to the University of Michigan Deep Blue
Data repository. No permission needed; it is an open research dataset.

Extract to:

```
E:\New folder\ai\data\raw\research\AI4SHIPWRECKS\
```

**One caveat to remember for your report:** this was recorded in Lake Huron —
**freshwater**. The lake bed does not look quite like Indian coastal seabed. It
is good data, but it is not the same environment, and saying so openly is
better than being asked about it.

---

# STEP 5 — Backup seafloor images  ⏱️ 10 min  🟡 your insurance

If the KLSG seafloor images never arrive, **this replaces them**, and it is a
public direct download with nothing to ask anyone for.

**Link:** <https://zenodo.org/records/10209445>

434,000 side-scan images of plain seafloor — sediment, rocks, marine life.

### ⚠️ Do not download all of it

It is enormous and you do not need it. **A few thousand images is plenty.**
Download one archive part, not the whole record.

Extract to:

```
E:\New folder\ai\data\raw\public\SEDIMENTS\
```

Tell me once it is there and I will write the sampling script — pulling a
balanced few thousand rather than dumping the lot into training.

---

# STEP 6 — Send Member 2 the handoff  ⏱️ 2 min  🔴 highest value per minute

**Do this today.** Member 2 is currently blocked on nothing at all, and does not
know it.

Send them **`docs/HANDOFF.md`** from this repo. It contains everything they need
to build the entire website — the data format, example files, and the rules for
displaying results — **without waiting for the AI to exist**.

Say this to them:

> "Build against the three example files in `ai/fixtures/`. The real AI produces
> the exact same format, so nothing on your side changes when the model is
> ready. Read `docs/HANDOFF.md` first — especially the five fields that matter."

Every hour they spend waiting is wasted, and there is no reason to wait.

---

# Do NOT download these

You will find them while searching. They look perfect. They are not.

**MDT marine debris** and **UATD** contain real underwater rubbish — tyres,
cans, bottles, chains. Tempting, because that is literally your problem.

**But they are the wrong kind of sonar.** They use *forward-looking* sonar,
which points ahead like a torch. Yours is *side-scan*, which sweeps sideways
across the seabed. Shadows — the main clue that something is sticking up off the
bottom — form completely differently. MDT was also recorded in a **water tank**,
not the sea.

Training on those and reporting the score as side-scan performance would be
dishonest, and a judge who knows sonar would spot it.

---

# When you are done

```bash
.venv/Scripts/python ai/scripts/inventory.py --verbose
```

This writes `ai/data/provenance/data_inventory.csv` — the Phase 0 deliverable
your plan asks for. It records what you actually have: real image counts, real
pixel sizes, label formats, and whether any GPS data came with it.

**Send me that output and I will start on the training pipeline.**

---

# If something goes wrong

| Problem | What to do |
|---|---|
| `inventory.py` says `ai/data/raw/ is empty` | Images are nested too deep or the folder name is wrong. Check the folder is spelled exactly as in the step. |
| Says `not in dataset_candidates.csv` | Folder name does not match. Rename it to the exact name in the step. |
| Reports a `MISMATCH` in counts | **Not an error — that is the tool doing its job.** It means the published claim disagrees with reality. Tell me the numbers. |
| `.rar` will not open | Use 7-Zip (free). But you should not need it — skip `SCTD2.0.rar`, it is empty. |
| Kaggle wants a phone number | Skip Step 3. Steps 2 and 5 cover it. |
| No reply from the KLSG email after 4 days | Assume no, and go with Step 5. Do not keep waiting. |

---

# Priority, if you are short on time

Only three of these actually matter:

1. **Step 6** — unblocks your teammate. Two minutes.
2. **Step 2 email** — the clock starts when you send it, not when you need it.
3. **Step 1 SCTD** — the dataset you will actually train on first.

Steps 3, 4 and 5 can wait until tomorrow.
