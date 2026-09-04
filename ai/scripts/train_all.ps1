# Run the whole training pipeline unattended: train -> calibrate -> background eval.
#
#   .\ai\scripts\train_all.ps1 -Name gv2-yolo11s
#   .\ai\scripts\train_all.ps1 -Name gv2-yolo11s -Resume
#   .\ai\scripts\train_all.ps1 -Name gv-yolo11s -SkipTrain    # run only the post-steps
#
# Everything is logged to ai/experiments/<Name>.pipeline.log, so you can close
# the terminal's scrollback and still know what happened.
#
# ASCII only in this file on purpose. The default shell here is PowerShell 5.1,
# which reads a BOM-less UTF-8 file as cp1252, so a single em dash decodes into
# a curly quote and PowerShell treats curly quotes as real string delimiters.
# One dash in a comment once opened an unterminated string and the parser
# reported the error 54 lines away.

param(
    [Parameter(Mandatory = $true)][string]$Name,
    [int]$Epochs = 40,
    [int]$Patience = 12,
    [string]$Model = "yolo11s",
    [int]$Batch = 4,
    [switch]$Resume,
    [switch]$SkipTrain
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Py = Join-Path $Root ".venv\Scripts\python.exe"
$ExpDir = Join-Path $Root "ai\experiments\$Name"
$Log = Join-Path $Root "ai\experiments\$Name.pipeline.log"

function Write-Step([string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message
    Write-Host $line
    Add-Content -Path $Log -Value $line -Encoding ascii
}

# ---------------------------------------------------------------------------
# Unattended failure policy for the TRAINING step.
#
# The trainer exits non-zero for reasons that deserve opposite responses, and
# treating them alike is what produced three concurrent trainers yesterday.
# Returns "retry" (resume from last.pt), "shrink" (halve the batch, then
# resume) or "stop" (abandon, skip the post-steps).
# ---------------------------------------------------------------------------
function Resolve-TrainFailure {
    param(
        [int]$ExitCode,
        [int]$EpochsDone,       # distinct epochs in results.csv right now
        [int]$EpochsBefore,     # distinct epochs before this attempt
        [int]$Attempt,          # 1-based
        [string]$TailOfLog      # last ~50 lines
    )

    # Hard cap. Three failures on one run is a broken config, not bad luck,
    # and an unattended loop that never gives up is worse than no loop.
    if ($Attempt -ge 3) { return "stop" }

    # OOM is deterministic: the same batch will fail at the same place every
    # time. Halving is the only response that changes the outcome, and only
    # once -- if batch 2 also OOMs, the image size or the model is the problem.
    if ($TailOfLog -match "out of memory") {
        if ($Attempt -eq 1) { return "shrink" }
        return "stop"
    }

    # A retry that completed no epoch accomplished nothing, so a second one
    # will accomplish nothing either. On the FIRST attempt this is still worth
    # one shot: the Windows dataloader crash kills a run mid-epoch and a plain
    # resume genuinely recovers it.
    if ($Attempt -gt 1 -and $EpochsDone -le $EpochsBefore) { return "stop" }

    # Progress was made and last.pt is good. This is the common case: four
    # rc=1 deaths in the gv-yolo11s run, every one recovered by --resume.
    return "retry"
}

function Get-EpochCount {
    # Distinct epoch numbers, NOT row count. Two trainers resuming from the
    # same checkpoint each append a row for the same epoch, so a naive count
    # overstates progress and a TOTAL stop fires an epoch early.
    $csv = Join-Path $ExpDir "results.csv"
    if (-not (Test-Path $csv)) { return 0 }
    $epochs = Get-Content $csv |
              Where-Object { $_ -match '^\d' } |
              ForEach-Object { ($_ -split ',')[0] } |
              Sort-Object -Unique
    return @($epochs).Count
}

# --- guards ----------------------------------------------------------------

if (-not (Test-Path $Py)) { throw "no interpreter at $Py" }
if (-not (Test-Path (Join-Path $Root "ai\data\processed\data.yaml"))) {
    throw "no dataset. Run ai/scripts/build_dataset.py first."
}

# A second trainer sharing 4 GB does not run half as fast, it collapses
# throughput to ~60 s/it and completes no epochs at all. Refuse to start one.
$live = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -like "*train.py*" }
if ($live) {
    throw "a trainer is already running (PID $($live.ProcessId)). Stop it with: taskkill /F /T /PID $($live.ProcessId)"
}

Write-Step "PIPELINE START  name=$Name model=$Model epochs=$Epochs batch=$Batch resume=$Resume"

# --- step 1: train ---------------------------------------------------------

if ($SkipTrain) {
    Write-Step "TRAIN SKIPPED (-SkipTrain)"
} else {
    $before = Get-EpochCount

    # Rebuilt every attempt, not built once: "shrink" changes $Batch, and an
    # array built before the loop would still carry the old value.
    function Build-TrainArgs([int]$b, [bool]$doResume) {
        $a = @(
            (Join-Path $Root "ai\scripts\train.py"),
            "--name", $Name, "--model", $Model,
            "--epochs", $Epochs, "--patience", $Patience,
            "--batch", $b,
            # workers 0 is load-bearing on Windows: worker processes die at
            # scale. It cost a run at 7,147 images after being fine at 1,335.
            "--workers", "0"
        )
        if ($doResume) { $a += "--resume" }
        return $a
    }

    # Hand-rolled tee, on purpose. Tee-Object has no -Encoding on Windows
    # PowerShell 5.1 (that parameter arrived in PowerShell 6), and plain
    # Tee-Object there writes UTF-16LE, which makes the log unreadable to grep
    # ("binary file matches") and to any plain-text parser. Cost a detour when
    # the per-class metrics could not be extracted from a finished run.
    # StreamWriter with AutoFlush gives ASCII on disk plus a log you can tail
    # from another window while the run is still going.
    $TrainLog = Join-Path $Root "ai\experiments\$Name.log"
    $useResume = [bool]$Resume
    $attempt = 1
    while ($true) {
        Write-Step "TRAIN attempt $attempt  batch=$Batch resume=$useResume"
        $sw = New-Object System.IO.StreamWriter($TrainLog, $true, [System.Text.Encoding]::ASCII)
        $sw.AutoFlush = $true
        try {
            & $Py @(Build-TrainArgs $Batch $useResume) 2>&1 | ForEach-Object {
                $line = $_.ToString()
                Write-Host $line
                $sw.WriteLine($line)
            }
            $rc = $LASTEXITCODE
        } finally {
            $sw.Dispose()
        }
        if ($rc -eq 0) { Write-Step "TRAIN OK rc=0 epochs=$(Get-EpochCount)"; break }

        $done = Get-EpochCount
        $tail = Get-Content $TrainLog -Tail 50 | Out-String
        $verdict = Resolve-TrainFailure -ExitCode $rc -EpochsDone $done -EpochsBefore $before `
                                        -Attempt $attempt -TailOfLog $tail
        Write-Step "TRAIN FAILED rc=$rc at epoch $done (was $before) -- policy says '$verdict'"

        if ($verdict -eq "stop") { Write-Step "PIPELINE ABORT"; exit 1 }
        if ($verdict -eq "shrink") {
            $Batch = [math]::Max(1, [int]($Batch / 2))
            Write-Step "SHRINK batch -> $Batch"
        }
        # Any relaunch resumes: last.pt holds the optimiser state, the epoch
        # counter and the LR schedule. Without it the run restarts at epoch 1
        # and overwrites everything.
        $useResume = $true
        $before = $done
        $attempt++
    }
}

# --- step 2: calibration ---------------------------------------------------
# Fitted on val, never on test. Until this file matches the current weights the
# pipeline caps uncertainty at "medium" and refuses to claim "low".

$best = Join-Path $ExpDir "weights\best.pt"
if (-not (Test-Path $best)) { Write-Step "no best.pt at $best -- stopping"; exit 1 }

Write-Step "CALIBRATE on val"
& $Py (Join-Path $Root "ai\scripts\fit_calibration.py") --weights $best --device 0
if ($LASTEXITCODE -ne 0) { Write-Step "CALIBRATE FAILED rc=$LASTEXITCODE" } else { Write-Step "CALIBRATE OK" }

# --- step 3: artificial-vs-natural false-positive rate ----------------------
# The headline number for the problem statement: how often the detector cries
# wolf on verified-empty seabed. Batch 8, not the script's default 32, because
# 4 GB does not reliably hold 32 at 640.

Write-Step "BACKGROUND EVAL on test"
& $Py (Join-Path $Root "ai\scripts\evaluate_background.py") --weights $best --split test --batch 8
if ($LASTEXITCODE -ne 0) { Write-Step "BACKGROUND EVAL FAILED rc=$LASTEXITCODE" } else { Write-Step "BACKGROUND EVAL OK" }

# --- summary ---------------------------------------------------------------

Write-Step "PIPELINE DONE"
$testMetrics = Join-Path $ExpDir "test_metrics.json"
if (Test-Path $testMetrics) {
    Write-Host "`nTEST metrics (quote these, never the validation figures):"
    Get-Content $testMetrics
}
Write-Host "`nArtifacts in ai/experiments/$Name  |  log: ai/experiments/$Name.pipeline.log"
