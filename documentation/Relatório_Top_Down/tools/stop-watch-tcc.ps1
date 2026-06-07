[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path $scriptDir ".watch-tcc.pid"

if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Host "Nenhum PID de watcher encontrado."
    exit 0
}

$pidText = Get-Content -LiteralPath $pidFile -Raw
$processId = 0
if (-not [int]::TryParse($pidText.Trim(), [ref]$processId)) {
    Remove-Item -LiteralPath $pidFile -Force
    Write-Host "Arquivo PID invalido removido."
    exit 0
}

$process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
if ($process -and $process.CommandLine -like "*watch-tcc.ps1*") {
    Stop-Process -Id $processId -Force
    Write-Host "Watcher do TCC encerrado. PID: $processId"
}
else {
    Write-Host "Watcher nao estava ativo."
}

Remove-Item -LiteralPath $pidFile -Force
