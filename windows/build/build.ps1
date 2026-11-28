# Builds PyCmd.exe.
#
#     powershell -ExecutionPolicy Bypass -File windows\build\build.ps1
#
# Run it from the repository root. It makes a virtual environment, installs
# what the build needs into it, runs the checks that do not need a window, and
# leaves dist\PyCmd.exe behind with its SHA-256 printed.
#
# Nothing here touches the machine outside the repository folder: the venv is
# .build-venv in the checkout and is safe to delete.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root

Write-Host "PyCmd for Windows - build" -ForegroundColor Cyan
Write-Host "repository: $root"

# -- python ------------------------------------------------------------------

$python = "python"
try {
    $version = & $python --version 2>&1
} catch {
    Write-Error "Python is not on the PATH. Install 3.11 or newer: winget install Python.Python.3.13"
    exit 1
}
Write-Host "python:     $version"

$venv = Join-Path $root ".build-venv"
if (-not (Test-Path $venv)) {
    Write-Host "making a build environment..."
    & $python -m venv $venv
}
$venvPython = Join-Path $venv "Scripts\python.exe"

Write-Host "installing what the build needs..."
& $venvPython -m pip install --quiet --upgrade pip
& $venvPython -m pip install --quiet -r windows\build\requirements.txt

# -- checks ------------------------------------------------------------------

Write-Host ""
Write-Host "running the checks..." -ForegroundColor Cyan
& $venvPython tools\test_windows.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "the checks did not pass, so nothing was built"
    exit 1
}

# -- the PyCmd engine (optional) ---------------------------------------------
# PyCmd 2's fast engine: lang/ as one jar plus a small Java runtime, bundled as
# pcmd-engine/. Needs a JDK 17+ on the PATH; without one the exe still works and
# runs PyCmd on its built-in engine.

if ((Get-Command java -ErrorAction SilentlyContinue) -and (Get-Command jlink -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host "building the PyCmd engine..." -ForegroundColor Cyan
    & "$root\gradlew.bat" -p lang jar --no-daemon
    if ($LASTEXITCODE -eq 0) {
        if (Test-Path "$root\pcmd-engine") { Remove-Item -Recurse -Force "$root\pcmd-engine" }
        New-Item -ItemType Directory -Force "$root\pcmd-engine" | Out-Null
        Copy-Item "$root\lang\build\libs\pcmd.jar" "$root\pcmd-engine\pcmd.jar"
        jlink --add-modules java.base,jdk.crypto.ec --strip-debug --no-man-pages --no-header-files --output "$root\pcmd-engine\runtime"
    } else {
        Write-Warning "the PyCmd engine did not build - PyCmd will use its built-in engine"
    }
} else {
    Write-Warning "no JDK on the PATH - building without the fast PyCmd engine"
}

# -- build -------------------------------------------------------------------

Write-Host ""
Write-Host "building..." -ForegroundColor Cyan
if (Test-Path "$root\build") { Remove-Item -Recurse -Force "$root\build" }
& $venvPython -m PyInstaller windows\build\pycmd.spec --noconfirm --distpath dist-windows\build
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller failed"
    exit 1
}

$exe = Join-Path $root "dist-windows\build\PyCmd.exe"
if (-not (Test-Path $exe)) {
    Write-Error "the build reported success but produced no exe"
    exit 1
}

$size = (Get-Item $exe).Length
$hash = (Get-FileHash $exe -Algorithm SHA256).Hash.ToLower()

Write-Host ""
Write-Host "built: $exe" -ForegroundColor Green
Write-Host ("size:  {0:N1} MB" -f ($size / 1MB))
Write-Host "sha256: $hash"
Write-Host ""
Write-Host "To publish it, put it in dist-windows\ and run:"
Write-Host "  python tools\make_latest_windows.py dist-windows\PyCmd-<version>.exe --notes ""...""" 
