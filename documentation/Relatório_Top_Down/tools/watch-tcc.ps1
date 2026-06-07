[CmdletBinding()]
param(
    [int]$IntervalSeconds = 1,
    [int]$DebounceMilliseconds = 750
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$reportDir = Resolve-Path (Join-Path $scriptDir "..")
$compileScript = Join-Path $scriptDir "compile-tcc.ps1"
$mainPdf = Join-Path $reportDir "PRINCIPAL.pdf"
$extensions = @(".tex", ".bib", ".png", ".jpg", ".jpeg", ".pdf", ".svg")

function Test-WatchedSourceFile {
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

function Get-WatchedSnapshot {
    Get-ChildItem -LiteralPath $reportDir -Recurse -File |
        Where-Object { Test-WatchedSourceFile $_ } |
        Sort-Object FullName |
        ForEach-Object {
            "{0}|{1}|{2}" -f $_.FullName, $_.Length, $_.LastWriteTimeUtc.Ticks
        }
}

function Invoke-TccCompile {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $compileScript
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "A compilacao falhou. Corrija o erro acima; o watcher continuara ativo."
    }
}

Write-Host "Watcher do TCC ativo em: $reportDir"
Write-Host "PDF oficial: $mainPdf"
Write-Host "Pressione Ctrl+C para encerrar."

Invoke-TccCompile
$lastSnapshot = @(Get-WatchedSnapshot)

while ($true) {
    Start-Sleep -Seconds $IntervalSeconds
    $currentSnapshot = @(Get-WatchedSnapshot)

    if (Compare-Object -ReferenceObject $lastSnapshot -DifferenceObject $currentSnapshot) {
        Start-Sleep -Milliseconds $DebounceMilliseconds
        $stableSnapshot = @(Get-WatchedSnapshot)
        Write-Host "Alteracao detectada. Recompilando..."
        Invoke-TccCompile
        $lastSnapshot = @(Get-WatchedSnapshot)
    }
}
