[CmdletBinding()]
param(
    [int]$IntervalSeconds = 5
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$reportDir = Resolve-Path (Join-Path $scriptDir "..")
$startWatchScript = Join-Path $scriptDir "start-watch-tcc.ps1"
$compileScript = Join-Path $scriptDir "compile-tcc.ps1"
$pidFile = Join-Path $scriptDir ".watch-tcc.pid"
$mainPdf = Join-Path $reportDir "PRINCIPAL.pdf"
$extensions = @(".tex", ".bib", ".png", ".jpg", ".jpeg", ".pdf", ".svg")

function Test-WatcherProcess {
    param([int]$ProcessId)

    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
    return $process -and $process.CommandLine -like "*watch-tcc.ps1*"
}

function Ensure-Watcher {
    $watcherOk = $false

    if (Test-Path -LiteralPath $pidFile) {
        $pidText = Get-Content -LiteralPath $pidFile -Raw
        $processId = 0
        if ([int]::TryParse($pidText.Trim(), [ref]$processId)) {
            $watcherOk = Test-WatcherProcess -ProcessId $processId
        }
    }

    if (-not $watcherOk) {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $startWatchScript | Out-Null
        Write-Host "Watcher verificado/reiniciado."
    }
}

function Test-SourceFile {
    param([System.IO.FileInfo]$File)

    if ($File.FullName -like (Join-Path $reportDir "build\*")) {
        return $false
    }

    if ($File.FullName -like (Join-Path $reportDir "tools\*")) {
        return $false
    }

    if ($File.FullName -ieq $mainPdf) {
        return $false
    }

    if ($File.Name -match "^(PRINCIPAL|modelocapa|folhaderosto|folhaaprova|ficha|dedicatoria|agradecimentos|epigrafe|resumos|siglas|apendices)\.(aux|log|toc|lof|bbl|blg|brf|idx|ind|ilg|fls|fdb_latexmk|synctex\.gz)$") {
        return $false
    }

    return $extensions -contains $File.Extension.ToLowerInvariant()
}

function Get-NewerSourceThanPdf {
    if (-not (Test-Path -LiteralPath $mainPdf)) {
        return Get-ChildItem -LiteralPath $reportDir -Recurse -File | Where-Object { Test-SourceFile $_ } | Select-Object -First 1
    }

    $pdfTime = (Get-Item -LiteralPath $mainPdf).LastWriteTimeUtc
    return Get-ChildItem -LiteralPath $reportDir -Recurse -File |
        Where-Object { (Test-SourceFile $_) -and $_.LastWriteTimeUtc -gt $pdfTime } |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1
}

Write-Host "Guardiao do PDF do TCC ativo."
Write-Host "PDF oficial: $mainPdf"

while ($true) {
    Ensure-Watcher

    $newerSource = Get-NewerSourceThanPdf
    if ($newerSource) {
        Write-Host "Fonte mais nova que o PDF detectada: $($newerSource.FullName)"
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $compileScript
    }

    Start-Sleep -Seconds $IntervalSeconds
}
