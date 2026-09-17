# Build brief: the Training Spooler ("a printer for training jobs")

> Side project, separate from SIH26057 GhostNet-AI delivery. This file is the
> handoff prompt: paste it into a fresh session, or hand it to a contributor.
> It is written to be read cold, with no memory of the conversation that
> produced it.

---

## 1. The idea, in the owner's words

> "Drag and drop a dataset, give it the commands (which differ per model type),
> and it trains on its own in a loop — like a printer we keep giving papers and
> it prints out different data as per input. And it keeps trying if the training
> fails."

Build that. A local, single-machine **training job spooler**: a queue you drop
work into, which runs jobs unattended, one at a time, retries intelligently when
they die, records what happened, and never stalls.

## 2. Why this framing and not "AutoML"

The first phrasing of this idea was AutoML-shaped: *point it at a folder and it
figures out the model type.* That version's hard problem is inferring task and
label format from an arbitrary dropped directory — an open research problem
dressed as a feature.

**The user supplies the commands.** That single constraint deletes the inference
problem. What remains is a spooler: a spool directory, a runner loop, a
subprocess per job, a log per job. **The runner must never parse or validate
model-specific fields.** It forwards them verbatim to the training script named
in the job. Any temptation to "understand" the job's hyperparameters is scope
creep and should be refused in review.

## 3. What already exists (READ THESE BEFORE WRITING CODE)

This is not a greenfield build. The single-job version of the spooler is already
written and battle-tested, and the spooler is its generalization to N jobs.

| Path | What it already solves |
| --- | --- |
| `ai/scripts/train_all.ps1` | Unattended one-job pipeline: train → calibrate → background eval, with retry policy, tee'd ASCII logging, and a concurrent-trainer guard. **The single most important file in this brief.** |
| `ai/scripts/train.py` | Detection trainer. Writes `ai/experiments/<name>/`. Has `--resume`, `--dry-run`, `--force`, `--allow-dataset-drift`. |
| `ai/scripts/train_net_seg.py` | Segmentation trainer. Deliberately a *separate* script with different defaults (300 epochs, patience 60) — proof that "one trainer to rule them all" is the wrong model. |
| `ai/experiments/gv-yolo11s/provenance.json` | The per-run record the spooler should write automatically: git commit, resolved args, torch version, GPU name, dataset sources, per-split sizes, per-class box counts. |
| `ai/experiments/*.pipeline.log` | The log format to keep. |

### 3.1 Knowledge to port, not rediscover

Lift these out of `train_all.ps1` into the spooler core. Each cost a real run.

1. **Failure triage, not blanket retry.** `Resolve-TrainFailure` returns one of
   three verdicts from (exit code, epochs done, epochs before, attempt number,
   last ~50 log lines):
   - log tail matches `out of memory` and attempt 1 → **shrink** (halve batch, resume)
   - `out of memory` again → **stop** (image size or model is the problem, not luck)
   - attempt > 1 and no new epoch completed → **stop** (a retry that accomplishes nothing will accomplish nothing twice)
   - attempt >= 3 → **stop** (three failures is a broken config, not bad luck)
   - otherwise → **retry** with `--resume` (the common case: four rc=1 deaths in the gv-yolo11s run, every one recovered by a plain resume)
2. **Every relaunch resumes.** `last.pt` holds optimiser state, the epoch counter
   and the LR schedule. Relaunching without `--resume` restarts at epoch 1 and
   *overwrites the previous attempt's artifacts.*
3. **Count distinct epoch numbers, never CSV rows.** Two processes resuming from
   one checkpoint each append a row for the same epoch; row-counting overstates
   progress and fires a stop an epoch early.
4. **One print head.** 4 GB VRAM (RTX 3050 Laptop) does not degrade gracefully:
   a second concurrent trainer collapses throughput to ~60 s/it and completes
   *zero* epochs. Three concurrent trainers have already happened once. Serial
   execution is a hard invariant, enforced by a lock, not by convention.
5. **`--workers 0` on Windows is load-bearing.** Dataloader workers die at scale;
   it cost a run at 7,147 images after being fine at 1,335.
6. **ASCII-only logs, written via StreamWriter with AutoFlush.** `Tee-Object` on
   PowerShell 5.1 writes UTF-16LE, which makes logs unreadable to grep
   ("binary file matches") and to any plain-text parser. Also: keep PowerShell
   sources ASCII-only — a BOM-less UTF-8 em dash decodes under cp1252 into a
   curly quote, which PS 5.1 treats as a string delimiter, and the parse error
   is reported ~54 lines away from the offending character.
7. **Isolation.** Runs write `ai/experiments/<name>/` only. Nothing unattended
   may write `ai/models/` — a shipped model's calibration was once refitted
   against experiment weights and had to be undone by hand.

## 4. Scope

### 4.1 In scope (v1)

- A **spool directory** of jobs, each self-describing on disk.
- A **runner daemon**: pick the oldest queued job, run it, apply the failure
  policy, write results, move to the next. Survives job crashes.
- A **submit path**: CLI (`spool submit`) plus drag-and-drop (see 4.3).
- **Per-job logs and provenance**, written automatically.
- **State visible on disk** — `ls` the spool and you know what is happening,
  with no daemon running and no database to query.
- Correct behaviour when the machine reboots mid-queue.

### 4.2 Explicitly NOT in scope

- Inferring anything about the model, task, or label format.
- Distributed / multi-GPU / multi-machine scheduling.
- Hyperparameter search or sweeps (v2 at the earliest; see §10).
- A cloud service, accounts, or auth.
- Editing datasets. The spooler consumes them; converters stay separate scripts.

### 4.3 UI, in order of build

1. **CLI first** (`submit`, `ls`, `logs`, `cancel`, `retry`, `pause`, `resume`).
   Everything must be doable without a GUI, because the GUI will be the part
   that breaks.
2. **Gradio / small web page second** — drag-and-drop onto a page is the
   "printer" feel with none of the desktop packaging pain, and it gives a live
   log tail for free.
3. Desktop shell (Tauri/Electron) only if it is still wanted afterwards. It is
   polish, not capability.

## 5. Architecture

```
spool/
  queued/        <job-id>/  job.yaml  [dataset/ or a path pointer]
  running/       <job-id>/  job.yaml  claim.json
  done/          <job-id>/  job.yaml  result.json  job.log
  failed/        <job-id>/  job.yaml  result.json  job.log
  cancelled/     <job-id>/
  runner.lock
```

- **State is the directory a job sits in.** Transitions are atomic directory
  renames (`os.replace`), which within one filesystem is atomic on both Windows
  and POSIX. No database, no state field to drift out of sync with reality.
- `<job-id>` = `<UTC timestamp>-<short slug>-<4 random chars>`, so the queue
  sorts lexicographically by submission time and `ls` *is* the queue order.
- **Datasets are referenced by absolute path by default, copied only on request**
  (`copy_dataset: true`). Copying a 12,472-image dataset per job is minutes of
  I/O and gigabytes of disk for no benefit when the path is stable. But record a
  **dataset fingerprint** either way (see §7.2).

### 5.1 The runner loop

```
acquire runner.lock (exclusive; pid + hostname + start time inside)
loop forever:
    if paused: sleep, continue
    job = oldest dir in queued/   (none -> sleep poll_interval, continue)
    move job -> running/, write claim.json (pid, attempt, started_utc)
    for attempt in 1..max_attempts:
        launch the job's command as a SUBPROCESS, tee stdout+stderr to job.log
        if rc == 0: break
        verdict = triage(rc, progress_now, progress_before, attempt, log_tail)
        record the verdict in job.log AND result.json
        if verdict == stop: break
        if verdict == shrink: mutate the retry args per the job's shrink rule
        set resume for the next attempt
    verify artifacts (see `expect:` in §6)
    move job -> done/ or failed/, write result.json
release lock
```

Non-negotiables:

- **Subprocess, always.** A segfaulting trainer must kill the job, not the runner.
- **The runner is single-threaded and holds one lock.** If the lock is held by a
  live PID, refuse to start with an actionable message (the existing script's
  `taskkill /F /T /PID <pid>` hint is the right tone). If the PID is dead, the
  lock is stale — reclaim it and log that you did.
- **A crashed job must never stall the queue.** After `max_attempts` it goes to
  `failed/` and the loop continues. This is the whole point of the project.
- **Crash recovery on startup:** anything in `running/` whose `claim.json` PID is
  not alive gets *requeued once* (with `attempt` carried forward and
  `resume: true`), or moved to `failed/` if it has already been requeued. Never
  requeue in an unbounded loop.

## 6. The job contract (`job.yaml`)

Design goal: the runner reads only the outer envelope; everything under
`command` is forwarded blind.

```yaml
# --- envelope: the runner reads these -------------------------------
name: gv8-netseg-lr-sweep-a       # experiment name, also the log prefix
kind: yolo-seg                    # a free-text LABEL for humans/filtering.
                                  # The runner MUST NOT branch on it.
priority: 0                       # higher runs first; ties break by age
max_attempts: 3
timeout_minutes: 900              # wall-clock kill switch, per attempt
depends_on: []                    # job ids that must reach done/ first
notify_on: [done, failed]

# --- how to run it: forwarded verbatim ------------------------------
command:
  interpreter: .venv/Scripts/python.exe   # relative to repo root
  script: ai/scripts/train_net_seg.py
  args:
    --name: gv8-netseg-lr-sweep-a
    --data: E:/New folder/ai/data/net_seg/data.yaml
    --epochs: 300
    --batch: 4
    --workers: 0

# --- retry semantics: the job tells the runner HOW to retry ----------
retry:
  resume_flag: --resume           # appended on every relaunch after the first
  shrink:
    arg: --batch                  # what "shrink" halves
    floor: 1
  progress_file: ai/experiments/gv8-netseg-lr-sweep-a/results.csv
  progress_metric: distinct_first_column   # see §3.1.3

# --- what "finished" must have produced -----------------------------
artifacts:
  dir: ai/experiments/gv8-netseg-lr-sweep-a
  expect:                         # missing => job is FAILED, even at rc=0
    - weights/best.pt
    - results.csv
```

`retry:` is the key design move. It keeps the runner model-agnostic while still
letting it do the smart thing: the *job* declares which flag means resume and
which flag to halve, so the runner can shrink a batch size without knowing what
a batch size is.

`expect:` exists because **rc=0 is not proof of success.** A trainer can exit
clean having written no weights. Verify the artifacts before declaring done.

## 7. Things that should be there but were not in the original idea

Ordered by how much they matter. §7.1–7.4 are close to required.

### 7.1 Preflight, before the job leaves `queued/`

Cheap checks that turn a 3 a.m. failure into an instant rejection at submit
time: interpreter exists; script exists; every path-shaped arg exists; the
dataset yaml parses and its `train`/`val` paths resolve; free disk >= a
configured floor; `nvidia-smi` reports the GPU and no foreign process holds
VRAM; the experiment name is not already used by a *different* job (silent
overwrite of a finished run is unrecoverable). Expose preflight as `--dry-run`
too, so a job can be validated without queueing it.

### 7.2 Provenance, extended and automatic

Grow `provenance.json` into a spooler-written record: everything already there,
plus **git commit AND dirty-tree state** (a metric from a dirty tree is not
reproducible — record the diff, or refuse to run, but never silently record the
clean commit), the resolved command line as actually executed, every retry and
its verdict, per-attempt wall clock, peak VRAM, and a **dataset fingerprint**
(hash of the sorted (relative path, size, mtime) list — cheap; full content hash
behind a flag). The fingerprint is what answers "was this the despeckled build?"
three weeks later — exactly the mistake that made `-Data` a mandatory-in-spirit
parameter in `train_all.ps1`.

### 7.3 A results index

After each job, append one row to `spool/results.csv` (or a small SQLite file):
job id, name, kind, dataset fingerprint, key metrics scraped from the job's own
`test_metrics.json`, wall clock, attempts, final verdict. The value of a spooler
is not running 20 jobs — it is *comparing* 20 jobs the next morning. Without an
index that comparison is 20 manual file opens. Scrape metrics via a per-`kind`
plugin so the *core* still knows nothing about models.

### 7.4 Notifications

A 7-hour job that finishes at 2 a.m. should say so. Simplest sufficient version:
a webhook URL and/or a Windows toast, fired on done/failed, carrying the name,
the verdict, wall clock, and a one-line metric summary. Make it a no-op when
unconfigured — never a startup requirement.

### 7.5 Timeout and thermal guards

A hung job that produces no epoch for N minutes is worse than a crashed one: it
holds the lock forever. Two watchdogs — absolute `timeout_minutes` per attempt,
and a **stall detector**: no new line in `job.log` for `stall_minutes` → kill and
triage as a failure. On a laptop GPU, also log temperature per epoch; if this
machine thermally throttles, a run's timings are uninterpretable without it.

### 7.6 Stage pipelines, because one job is already three steps

`train_all.ps1` is train → calibrate → background-eval, and each stage has its
own failure handling. Model a job as an **ordered list of stages** sharing one
name and artifact dir, with per-stage `continue_on_failure` (calibration failing
must not throw away trained weights). This also makes `depends_on` unnecessary
for the common case.

### 7.7 Ergonomics that decide whether it actually gets used

- `spool submit --from <finished-job-id> --set --batch=2` — most real jobs are a
  small edit of the last one. Retyping a 10-arg job invites typos.
- `spool logs -f <job>` — live tail from the CLI, without hunting the path.
- `spool ls` — one screen: queued with ETAs, running with progress and elapsed,
  the last few finished with verdicts.
- **ETA from history**: the results index knows the last run of this kind took
  625 s/epoch, so the queue can show "next slot free ~06:40". The single most
  satisfying feature to have, and nearly free once §7.3 exists.
- `spool pause` — drain the current job, then stop taking new ones. Needed when
  you want the GPU back for something interactive.
- Retention: `spool prune --keep-best` — checkpoint dirs are large and 20
  unattended runs will fill the disk. Never auto-delete; make it an explicit verb.

### 7.8 Testing, unusually hard here and unusually important

The unattended failure policy is the part that must work when nobody is
watching, and it is exercised only by rare, expensive events. So:

- Make triage a **pure function** of (rc, progress_now, progress_before,
  attempt, log_tail) and unit-test every branch in §3.1.1 against real log tails
  saved as fixtures. `ai/experiments/gv-yolo11s.crashed-0831.log` is one such
  real artifact — mine the existing logs for fixtures.
- Provide a **fake trainer** script that can be told to OOM at epoch 3, hang
  forever, exit 0 writing nothing, or succeed slowly. Every integration test
  (crash recovery, stale lock, stall detector, `expect:` verification) then runs
  against it in seconds, on CPU. Building this first is what makes the rest
  testable at all.
- The repo already has tests in `ai/tests/` — match their conventions.

## 8. Constraints of this machine

- Windows 11, PowerShell 5.1 as default shell (see §3.1.6 for the encoding trap).
- RTX 3050 Laptop, **4 GB VRAM**: `batch=4` at 640 px with AMP fits; 8 does not
  reliably. Strictly one job at a time.
- Python venv at `.venv/Scripts/python.exe`; torch 2.13.0+cu126.
- Reference workload: ~625 s/epoch × 40 epochs ≈ **7 hours** for a detection run
  on 12,472 images. This number is why the project exists — the GPU currently
  idles overnight between experiments because nobody wants to babysit it.
- Write it cross-platform where that is free (`pathlib`, `os.replace`,
  `subprocess`), but do not pay for portability nobody needs. Prefer Python for
  the core: `train_all.ps1`'s logic is sound, but PS 5.1 is a hostile host for it.

## 9. Milestones

- **M0 — fake trainer + triage as a pure, unit-tested function.** Nothing else
  is verifiable until this exists.
- **M1 — runner loop, on-disk states, lock, subprocess, per-job log.** Prove it
  by queueing three fake jobs where the middle one crashes, and watching the
  third still run.
- **M2 — `job.yaml` contract, preflight, `expect:` verification, `result.json`.**
- **M3 — CLI: submit / ls / logs -f / cancel / retry / pause.**
- **M4 — run a real job end to end.** The D2 net-seg run is the natural first
  customer: small, fast, real.
- **M5 — results index + ETA + notifications.**
- **M6 — Gradio drag-and-drop front end.**
- **M7 — stage pipelines; port `train_all.ps1` to a 3-stage job and retire the
  PowerShell path.**

Estimate from the original conversation: **a weekend for the CLI/Gradio
version**; the desktop shell is polish on top. M0–M4 is the honest weekend.

## 10. Deliberately deferred to v2

Sweeps (`for lr in [...]: submit`) — trivial once submit exists, and the reason
`--from ... --set` is in §7.7; multi-GPU; remote submission; auto-promotion of a
winning model (must stay a human decision — see the isolation rule in §3.1.7);
early-stopping a job because the index says it is underperforming a prior run.

## 11. Open decisions for the owner — DO NOT GUESS THESE

1. **Priority vs. strict FIFO.** A priority field is five lines and prevents "my
   quick 10-minute job is stuck behind a 7-hour run". It also permits starvation
   and complicates the ETA display. FIFO only, or priority with an age boost?
2. **Copy datasets into the spool, or reference by path?** Copying makes a job
   reproducible and immune to the dataset being rebuilt underneath it;
   referencing is instant and costs no disk. Which is the default?
3. **Can a `failed/` job ever block the queue?** The answer written into this
   brief is "never". Worth confirming: if job 5 depends on job 4's weights,
   running it against nothing is a wrong-answer bug, not merely a crash.
4. **Repo home:** a subdirectory of the GhostNet-AI repo, or its own repo? It is
   general-purpose infrastructure with no ghost-net content, which argues for its
   own repo — but every early user story lives in this one.
