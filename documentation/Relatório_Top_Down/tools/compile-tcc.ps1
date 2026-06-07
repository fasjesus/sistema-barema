[CmdletBinding()]
param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$reportDir = Resolve-Path (Join-Path $scriptDir "..")
$mainFile = "PRINCIPAL.tex"
$pdfFile = Join-Path $reportDir "PRINCIPAL.pdf"

function Find-Latexmk {
    $pathCommand = Get-Command "latexmk.exe" -ErrorAction SilentlyContinue
    if ($pathCommand) {
        return $pathCommand.Source
    }

    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\MiKTeX\miktex\bin\x64\latexmk.exe"),
        (Join-Path $env:ProgramFiles "MiKTeX\miktex\bin\x64\latexmk.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "MiKTeX\miktex\bin\x64\latexmk.exe")
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }

    return $null
}

$latexmk = Find-Latexmk
if (-not $latexmk) {
    throw "latexmk.exe nao foi encontrado no PATH nem na instalacao local esperada do MiKTeX. Verifique C:\Users\fdpc0\AppData\Local\Programs\MiKTeX\miktex\bin\x64."
}

if (-not (Test-Path -LiteralPath (Join-Path $reportDir $mainFile))) {
    throw "Arquivo principal nao encontrado: $(Join-Path $reportDir $mainFile)"
}

Push-Location $reportDir
try {
    if ($Clean) {
        & $latexmk -C $mainFile
        if ($LASTEXITCODE -ne 0) {
            throw "Falha ao limpar artefatos LaTeX com latexmk. Codigo: $LASTEXITCODE"
        }
    }

    & $latexmk -pdf -g -f -synctex=1 -interaction=nonstopmode -file-line-error $mainFile
    $latexExitCode = $LASTEXITCODE

    if (-not (Test-Path -LiteralPath $pdfFile)) {
        throw "Compilacao terminou, mas o PDF esperado nao foi encontrado: $pdfFile"
    }

    Write-Host "PDF atualizado: $pdfFile"
    if ($latexExitCode -ne 0) {
        Write-Warning "latexmk retornou codigo $latexExitCode. O PDF foi gerado, mas ha warnings/pendencias no log."
    }
}
finally {
    Pop-Location
}
