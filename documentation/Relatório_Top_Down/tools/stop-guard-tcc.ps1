[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path $scriptDir ".guard-tcc.pid"

if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Host "Nenhum PID de guardiao encontrado."
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
if ($process -and $process.CommandLine -like "*guard-tcc-pdf.ps1*") {
    Stop-Process -Id $processId -Force
    Write-Host "Guardiao do TCC encerrado. PID: $processId"
}
else {
    Write-Host "Guardiao nao estava ativo."
}

Remove-Item -LiteralPath $pidFile -Force
