<#
    Stop the GhostNet-AI API and web console.

    PostgreSQL is deliberately left alone: it is a shared Windows service set
    to Automatic, other things on this machine may be using it, and stopping it
    needs elevation. Shutting down an app should not take the database with it.

    Stops by LISTENING PORT rather than by process name, because the usual
    approaches do not work here: `taskkill /IM node.exe` would also kill an
    editor's language server, and `pkill -f "next start"` matches nothing at
    all on Windows -- a real trap, since it fails silently and leaves the old
    server holding the port while you think you stopped it.
#>

$ErrorActionPreference = 'Stop'

function Stop-Port ($port, $label) {
    $pids = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
    if (-not $pids) {
        Write-Host "  $label (port $port) was not running" -ForegroundColor DarkGray
        return
    }
    foreach ($processId in $pids) {
        try {
            Stop-Process -Id $processId -Force -ErrorAction Stop
            Write-Host "  stopped $label (port $port, pid $processId)" -ForegroundColor Green
        } catch {
            Write-Host "  could not stop pid $processId on port $port : $_" -ForegroundColor Red
        }
    }
}

Write-Host ''
Write-Host '  GhostNet-AI - shutting down' -ForegroundColor White
Write-Host ''
Stop-Port 3000 'web console'
Stop-Port 8000 'API'
Write-Host ''
Write-Host '  PostgreSQL left running (shared Windows service).' -ForegroundColor DarkGray
Write-Host ''
