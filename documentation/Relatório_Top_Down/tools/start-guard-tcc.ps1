[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$guardScript = Join-Path $scriptDir "guard-tcc-pdf.ps1"
$reportDir = Resolve-Path (Join-Path $scriptDir "..")
$pidFile = Join-Path $scriptDir ".guard-tcc.pid"
$outLog = Join-Path $scriptDir ".guard-tcc.out.log"
$errLog = Join-Path $scriptDir ".guard-tcc.err.log"

function Test-GuardProcess {
    param([int]$ProcessId)

    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
    return $process -and $process.CommandLine -like "*guard-tcc-pdf.ps1*"
}

if (Test-Path -LiteralPath $pidFile) {
    $existingPidText = Get-Content -LiteralPath $pidFile -Raw
    $existingPid = 0
    if ([int]::TryParse($existingPidText.Trim(), [ref]$existingPid) -and (Test-GuardProcess -ProcessId $existingPid)) {
        Write-Host "Guardiao do TCC ja esta ativo. PID: $existingPid"
        Write-Host "PDF oficial: $(Join-Path $reportDir 'PRINCIPAL.pdf')"
        exit 0
    }
}

$process = Start-Process -FilePath "powershell.exe" `
    -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $guardScript) `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -WindowStyle Hidden `
    -PassThru

Set-Content -LiteralPath $pidFile -Value $process.Id -Encoding ASCII

Write-Host "Guardiao do TCC iniciado. PID: $($process.Id)"
Write-Host "PDF oficial: $(Join-Path $reportDir 'PRINCIPAL.pdf')"
Write-Host "Log: $outLog"
