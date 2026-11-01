#Requires -Version 5.1
<#
.SYNOPSIS
    Build the portable Persian Calendar Widget onedir distribution.

.DESCRIPTION
    Runs the test suite, then builds with PyInstaller.  The packaged executable
    is smoke-tested and a JSON report is written to the temporary directory.
#>
[CmdletBinding()]
param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Spec = Join-Path $Root "packaging\PersianCalendarWidget.spec"
$Exe = Join-Path $Root "dist\PersianCalendarWidget\PersianCalendarWidget.exe"

if (-not (Test-Path $Python)) {
    throw "Virtual environment not found: $Python"
}
if (-not (Test-Path $Spec)) {
    throw "Spec file not found: $Spec"
}
$Version = (& $Python -c "from app import __version__; print(__version__)").Trim()
$Archive = Join-Path $Root "dist\PersianCalendarWidget-$Version-portable.zip"

Push-Location $Root
try {
    if (-not $SkipTests) {
        Write-Host "Running tests..."
        & $Python -m pytest -q
        if ($LASTEXITCODE -ne 0) {
            throw "Tests failed (exit code $LASTEXITCODE)."
        }
    }

    Write-Host "Building onedir distribution..."
    & $Python -m PyInstaller --noconfirm --clean $Spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed (exit code $LASTEXITCODE)."
    }

    if (-not (Test-Path $Exe)) {
        throw "Packaged executable not found: $Exe"
    }

    $Report = Join-Path $env:TEMP "pcw-packaged-smoke.json"
    if (Test-Path $Report) {
        Remove-Item $Report -Force
    }
    Write-Host "Smoke-testing packaged executable..."
    $Process = Start-Process -FilePath $Exe `
        -ArgumentList @("--smoke-test", "--smoke-report", $Report) `
        -Wait -PassThru
    if ($Process.ExitCode -ne 0) {
        throw "Packaged smoke test failed (exit code $($Process.ExitCode))."
    }
    if (-not (Test-Path $Report)) {
        throw "Packaged smoke report was not written: $Report"
    }
    $Result = Get-Content $Report -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $Result.ok) {
        throw "Packaged smoke test reported failure. See $Report"
    }

    Write-Host "Creating portable ZIP..."
    Compress-Archive `
        -Path (Join-Path $Root "dist\PersianCalendarWidget") `
        -DestinationPath $Archive `
        -CompressionLevel Optimal `
        -Force

    Write-Host ""
    Write-Host "Build complete: $Root\dist\PersianCalendarWidget\"
    Write-Host "Executable:    $Exe"
    Write-Host "Portable ZIP:  $Archive"
    Write-Host "Smoke report:  $Report"
}
finally {
    Pop-Location
}
