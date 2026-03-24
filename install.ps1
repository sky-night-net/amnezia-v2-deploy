<#
.SYNOPSIS
AmneziaWG v2 Premium - Installer / Auto-Updater
Powered by SkyKnight Network

.DESCRIPTION
This script installs the AmneziaWG terminal application on Windows.
#>

$ErrorActionPreference = "Continue"

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "   AMNEZIA v2 — AUTO INSTALLER (Windows)      " -ForegroundColor Cyan
Write-Host "          Powered by SkyKnight Network          " -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

# ─── 1. Check Dependencies ────────────────────────────────────────────────────────
Write-Host "[1/3] Checking dependencies..." -ForegroundColor Cyan

# Check Python3 or Python
$pythonCmd = "python"
if (-not (Get-Command "python3" -ErrorAction SilentlyContinue)) {
    if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
        Write-Host ""
        Write-Host "[✗] Python is not installed or not in your PATH." -ForegroundColor Red
        Write-Host "Please download Python from https://www.python.org/downloads/" -ForegroundColor Yellow
        Write-Host "CRITICAL: Check the box 'Add Python to PATH' during installation!" -ForegroundColor Yellow
        Write-Host "Or install via winget: winget install Python.Python.3.11" -ForegroundColor Gray
        Write-Host ""
        Read-Host "Press Enter to close this window..."
        return
    }
} else {
    $pythonCmd = "python3"
}

$pyVer = & $pythonCmd --version
Write-Host "[✓] $pyVer" -ForegroundColor Green

# Check Git
if (-not (Get-Command "git" -ErrorAction SilentlyContinue)) {
        Write-Host ""
        Write-Host "[✗] Git is not installed or not in your PATH." -ForegroundColor Red
        Write-Host "Please download Git from https://git-scm.com/download/win" -ForegroundColor Yellow
        Write-Host "Or install via winget: winget install Git.Git" -ForegroundColor Gray
        Write-Host ""
        Read-Host "Press Enter to close this window..."
        return
}
Write-Host "[✓] Git ready" -ForegroundColor Green

# ─── 2. Fetch/Update Source ───────────────────────────────────────────────────────
$InstallDir = "$env:USERPROFILE\.amnezia-v2"
$RepoUrl = "https://github.com/sky-night-net/amnezia-v2-deploy.git"

Write-Host "`n[2/3] Installing AmneziaWG CLI..." -ForegroundColor Cyan

if (Test-Path "$InstallDir\.git") {
    Write-Host "      Already installed. Pulling latest updates..." -ForegroundColor Yellow
    Set-Location $InstallDir
    & git pull --ff-only --quiet
    Write-Host "[✓] Updated successfully." -ForegroundColor Green
} else {
    Write-Host "      Cloning repository to $InstallDir..."
    & git clone --depth=1 --quiet $RepoUrl $InstallDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[✗] Failed to clone the repository. Check your internet connection." -ForegroundColor Red
        Read-Host "Press Enter to close this window..."
        return
    }
    Write-Host "[✓] Installed successfully." -ForegroundColor Green
}

# ─── 3. Setup Python environment and launcher ─────────────────────────────────────
Write-Host "`n[3/3] Setting up environment..." -ForegroundColor Cyan
Set-Location $InstallDir

try {
    & $pythonCmd -m pip install -q paramiko bcrypt requests
    Write-Host "[✓] Python modules installed." -ForegroundColor Green
} catch {
    Write-Host "[!] Could not install optional modules, they may be present already." -ForegroundColor Yellow
}

# Create a local .bat script for easy access
$BatPath = "$InstallDir\amnezia.bat"
$BatContent = "@echo off`r`ncd /d `"$InstallDir`"`r`n$pythonCmd amnezia-cli.py %*"
Set-Content -Path $BatPath -Value $BatContent

Write-Host "==============================================" -ForegroundColor Green
Write-Host " ✅ INSTALLATION COMPLETE!" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
Write-Host ""
Write-Host "To run the application again in the future, just type one of these:" -ForegroundColor Gray
Write-Host "  1) & `"$BatPath`"" -ForegroundColor Cyan
Write-Host "  2) cd $InstallDir ; python amnezia-cli.py" -ForegroundColor Cyan
Write-Host ""

# ─── Launch ───────────────────────────────────────────────────────────────────────
Write-Host "Launching AmneziaWG Premium Terminal..." -ForegroundColor Magenta
Start-Sleep -Seconds 1
& $pythonCmd amnezia-cli.py

# Added pause so terminal doesn't immediately vanish on first run if something fails in python
Read-Host "Press Enter to close this window..."

