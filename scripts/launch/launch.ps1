<#
    GhostNet-AI one-click launcher.

    Brings the whole stack up in the right order, waits for each piece to
    actually answer, and opens the console in a browser.

    It does NOT re-implement how the services start. `scripts/demo/*.cmd` are
    the single definition of that, and two constraints live in their comments
    that are easy to get wrong from memory:

      * the backend runs ONE uvicorn worker, because processing_service keeps
        its running-job table in process memory and the rate limiter is
        in-process too -- a second worker silently breaks job cancellation;
      * the frontend runs the PRODUCTION build, not `next dev`, because dev
        wedges under concurrent .next writes.

    This script therefore orchestrates and verifies; it delegates the actual
    launching. If how a service starts ever changes, it changes in one place.
#>

$ErrorActionPreference = 'Stop'

$Root      = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Backend   = Join-Path $Root 'app\backend'
$Frontend  = Join-Path $Root 'app\frontend'
$StartBack = Join-Path $Root 'scripts\demo\start-backend.cmd'
$StartFront= Join-Path $Root 'scripts\demo\start-frontend.cmd'

$ApiHealth = 'http://127.0.0.1:8000/api/v1/health'
$WebUrl    = 'http://localhost:3000'

function Say    ($m) { Write-Host "  $m" }
function Step   ($m) { Write-Host "`n[*] $m" -ForegroundColor Cyan }
function Good   ($m) { Write-Host "  OK  $m" -ForegroundColor Green }
function Warn   ($m) { Write-Host "  !   $m" -ForegroundColor Yellow }
function Fail   ($m) {
    Write-Host "`n  FAILED: $m" -ForegroundColor Red
    Write-Host "`nPress any key to close..."
    $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
    exit 1
}

function Test-Port ($port) {
    $null -ne (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

function Test-Url ($url) {
    try { (Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 }
    catch { $false }
}

function Wait-Url ($url, $label, $seconds = 90) {
    for ($i = 0; $i -lt $seconds; $i++) {
        if (Test-Url $url) { return $true }
        Start-Sleep -Seconds 1
        if ($i % 5 -eq 4) { Write-Host '.' -NoNewline }
    }
    Write-Host ''
    return $false
}

function Invoke-Build ($logPath) {
    <#
        npm is run through `cmd /c` with its own redirection rather than
        called directly.

        A native command writing to stderr under $ErrorActionPreference='Stop'
        raises a terminating NativeCommandError in PowerShell, and npm writes
        perfectly ordinary progress to stderr -- so calling it directly kills
        this script mid-build even when the build would have succeeded.
        Redirecting inside cmd keeps all of it out of PowerShell's error
        stream, and $LASTEXITCODE still carries npm's real exit code.
    #>
    Say 'building (about a minute)...'
    Push-Location $Frontend
    & cmd.exe /c "npm run build > `"$logPath`" 2>&1"
    $code = $LASTEXITCODE
    Pop-Location
    return $code
}

Write-Host ''
Write-Host '  GhostNet-AI' -ForegroundColor White
Write-Host '  Marine sonar intelligence console' -ForegroundColor DarkGray

# --------------------------------------------------------------------------
# 0. Preflight. Everything here is a one-time setup step the user may simply
#    not have done yet; each failure names the exact command that fixes it
#    rather than letting a service die with a stack trace in a window that
#    closes.
# --------------------------------------------------------------------------
Step 'Checking the install'

if (-not (Test-Path (Join-Path $Backend '.venv\Scripts\python.exe'))) {
    Fail "No Python venv at app\backend\.venv`n  Run:  cd app\backend; python -m venv .venv; .venv\Scripts\python.exe -m pip install -r requirements.txt; .venv\Scripts\python.exe -m pip install -e ..\..\ai"
}
if (-not (Test-Path (Join-Path $Frontend 'node_modules'))) {
    Fail "Frontend dependencies missing.`n  Run:  cd app\frontend; npm install"
}
if (-not (Test-Path (Join-Path $Backend '.env'))) {
    Warn 'app\backend\.env missing - copying from .env.example'
    Copy-Item (Join-Path $Backend '.env.example') (Join-Path $Backend '.env')
}
if (-not (Test-Path (Join-Path $Frontend '.env.local'))) {
    Warn 'app\frontend\.env.local missing - copying from .env.local.example'
    Copy-Item (Join-Path $Frontend '.env.local.example') (Join-Path $Frontend '.env.local')
}
Good 'venv, node_modules and config present'

# --------------------------------------------------------------------------
# 1. PostgreSQL. It is a Windows service here and set to Automatic, so the
#    normal case is "already running"; starting it may need elevation, which
#    is why a failure explains rather than throws.
# --------------------------------------------------------------------------
Step 'PostgreSQL'

$pg = Get-Service | Where-Object { $_.Name -like 'postgresql*' } | Select-Object -First 1
if (-not $pg) {
    if (Test-Port 5432) { Good 'something is serving 5432 (no Windows service found)' }
    else { Fail 'PostgreSQL is not installed as a service and nothing is listening on 5432.' }
} elseif ($pg.Status -ne 'Running') {
    Say "starting $($pg.Name)..."
    try { Start-Service $pg.Name; Good "$($pg.Name) started" }
    catch { Fail "Could not start $($pg.Name). Run this launcher as Administrator, or start the service manually." }
} else {
    Good "$($pg.Name) already running"
}

# --------------------------------------------------------------------------
# 2. Backend. Reuse anything already healthy rather than starting a second
#    copy -- the boot-time Task Scheduler entry may already have it up, and a
#    second uvicorn on the same port just fails noisily.
# --------------------------------------------------------------------------
Step 'Backend API (port 8000)'

if (Test-Url $ApiHealth) {
    Good 'already running and healthy'
} elseif (Test-Port 8000) {
    Fail 'Port 8000 is in use but /api/v1/health does not answer. Stop whatever holds it:  netstat -ano | findstr :8000'
} else {
    Say 'starting uvicorn in its own window...'
    Start-Process -FilePath 'cmd.exe' -ArgumentList '/k', "`"$StartBack`"" -WorkingDirectory $Backend
    Write-Host '  waiting' -NoNewline
    if (-not (Wait-Url $ApiHealth 'backend' 90)) {
        Fail 'Backend did not become healthy within 90s. Check the uvicorn window for the error.'
    }
    Good 'healthy'
}

# --------------------------------------------------------------------------
# 3. Frontend. `next start` serves a FROZEN build, so a source edit since the
#    last build is invisible until a rebuild -- the single most confusing
#    failure mode in this project, because the app looks fine and simply does
#    not contain your change. So: compare the newest source file against the
#    build marker, and rebuild when it is behind.
# --------------------------------------------------------------------------
Step 'Frontend (port 3000)'

$buildId = Join-Path $Frontend '.next\BUILD_ID'
$newestSource = Get-ChildItem -Path (Join-Path $Frontend 'src'), `
                                (Join-Path $Frontend 'package.json'), `
                                (Join-Path $Frontend 'next.config.mjs'), `
                                (Join-Path $Frontend 'tailwind.config.ts') `
                                -Recurse -File -ErrorAction SilentlyContinue |
                Sort-Object LastWriteTime -Descending | Select-Object -First 1

$needsBuild = $true
if (Test-Path $buildId) {
    $built = (Get-Item $buildId).LastWriteTime
    if ($newestSource -and $newestSource.LastWriteTime -le $built) { $needsBuild = $false }
}

if (-not $needsBuild) {
    Good 'build is current'
} else {
    if (Test-Port 3000) {
        # Rebuilding writes into the .next directory the running server is
        # serving from. Leaving it up produces 404s on JS chunks that look
        # like corruption, so it has to come down first.
        Warn 'sources changed since the last build - stopping the running server to rebuild'
        Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique |
            ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
        # Give the dying server time to release its handles on .next. Building
        # too soon after leaves a half-written build that fails with
        # "Cannot find module for page: /_document" -- observed, not theoretical.
        Start-Sleep -Seconds 5
    }

    $log = Join-Path $env:TEMP 'ghostnet-build.log'
    $code = Invoke-Build $log
    if ($code -ne 0) {
        # One retry from clean. Next's incremental cache is the usual culprit
        # when a build fails right after the server holding it was killed, and
        # a wiped .next costs a minute against a launcher that refuses to start.
        Warn 'build failed - clearing .next and retrying once'
        Remove-Item (Join-Path $Frontend '.next') -Recurse -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        $code = Invoke-Build $log
    }
    if ($code -ne 0) {
        Fail "Frontend build failed twice. Log: $log"
    }
    Good 'built'
}

if (Test-Url $WebUrl) {
    Good 'already serving'
} elseif (Test-Port 3000) {
    Fail 'Port 3000 is in use but not answering. Stop it:  netstat -ano | findstr :3000'
} else {
    # Port 3000 specifically: Next silently falls back to 3001 if it is taken,
    # and the backend's CORS then rejects every request, which surfaces in the
    # UI as "Unable to reach the server" -- indistinguishable from the backend
    # being down. The port check above is what keeps that from happening quietly.
    Say 'starting Next.js in its own window...'
    Start-Process -FilePath 'cmd.exe' -ArgumentList '/k', "`"$StartFront`"" -WorkingDirectory $Frontend
    Write-Host '  waiting' -NoNewline
    if (-not (Wait-Url $WebUrl 'frontend' 90)) {
        Fail 'Frontend did not answer within 90s. Check the Next.js window.'
    }
    Good 'serving'
}

# --------------------------------------------------------------------------
# 4. Open it.
# --------------------------------------------------------------------------
Step 'Opening the console'
Start-Process $WebUrl
Write-Host ''
Write-Host "  $WebUrl" -ForegroundColor White
Write-Host '  log in as  operator / operator123' -ForegroundColor DarkGray
Write-Host ''
Write-Host '  Two windows were opened for the backend and frontend.' -ForegroundColor DarkGray
Write-Host '  Close them, or run Stop-GhostNet.bat, to shut everything down.' -ForegroundColor DarkGray
Write-Host ''
Start-Sleep -Seconds 4
