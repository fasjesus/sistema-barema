[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$watchScript = Join-Path $scriptDir "watch-tcc.ps1"
$reportDir = Resolve-Path (Join-Path $scriptDir "..")
$pidFile = Join-Path $scriptDir ".watch-tcc.pid"
$outLog = Join-Path $scriptDir ".watch-tcc.out.log"
$errLog = Join-Path $scriptDir ".watch-tcc.err.log"

function Test-WatcherProcess {
    param([int]$ProcessId)

    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
    if (-not $process) {
        return $false
    }

    return $process.CommandLine -like "*watch-tcc.ps1*"
}

if (Test-Path -LiteralPath $pidFile) {
    $existingPidText = Get-Content -LiteralPath $pidFile -Raw
    $existingPid = 0
    if ([int]::TryParse($existingPidText.Trim(), [ref]$existingPid) -and (Test-WatcherProcess -ProcessId $existingPid)) {
        Write-Host "Watcher do TCC ja esta ativo. PID: $existingPid"
        Write-Host "PDF oficial: $(Join-Path $reportDir 'PRINCIPAL.pdf')"
        exit 0
    }
}

$process = Start-Process -FilePath "powershell.exe" `
    -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $watchScript) `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -WindowStyle Hidden `
    -PassThru

Set-Content -LiteralPath $pidFile -Value $process.Id -Encoding ASCII

Write-Host "Watcher do TCC iniciado. PID: $($process.Id)"
Write-Host "PDF oficial: $(Join-Path $reportDir 'PRINCIPAL.pdf')"
Write-Host "Log: $outLog"
