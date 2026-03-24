<#
.SYNOPSIS
AmneziaWG v2 Premium - Installer / Auto-Updater
Powered by Sky Night Network

.DESCRIPTION
This script installs the AmneziaWG terminal application on Windows.
#>

$ErrorActionPreference = "Continue"

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "   AMNEZIA v2 — AUTO INSTALLER (Windows)      " -ForegroundColor Cyan
Write-Host "          Powered by Sky Night Network          " -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

# ─── 1. Check Dependencies ────────────────────────────────────────────────────────
Write-Host "[1/3] Checking dependencies..." -ForegroundColor Cyan

# Check Python3 or Python
$pythonCmd = "python"
if (Get-Command "python3" -ErrorAction SilentlyContinue) {
    $pythonCmd = "python3"
}

$pyVer = & $pythonCmd --version 2>&1
if ($LASTEXITCODE -ne 0 -or [string]$pyVer -match "was not found" -or [string]::IsNullOrWhiteSpace($pyVer)) {
    Write-Host "`n[!] Python is not installed." -ForegroundColor Yellow
    $ans = Read-Host "Do you want to automatically install Python now via winget? (Y/n)"
    if ($ans -match "^[Nn]") {
        Write-Host "[✗] Python is required. Aborting." -ForegroundColor Red
        Read-Host "Press Enter to close this window..."
        return
    }
    Write-Host "`nInstalling Python 3.11 via winget..." -ForegroundColor Cyan
    & winget install Python.Python.3.11 --accept-package-agreements --accept-source-agreements --silent
    Write-Host "[✓] Python installed." -ForegroundColor Green
    
    # Refresh PATH locally for current session
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    $pythonCmd = "python"
    $pyVer = & $pythonCmd --version 2>&1
}

Write-Host "[✓] $pyVer" -ForegroundColor Green

$InstallDir = "$env:USERPROFILE\.amnezia-v2"
$ZipUrl = "https://github.com/sky-night-net/amnezia-v2-deploy/archive/refs/heads/main.zip"

Write-Host "`n[2/3] Fetching AmneziaWG CLI (Native ZIP Method)..." -ForegroundColor Cyan

$TempZip = "$env:TEMP\amnezia-v2-main.zip"
$ExtractDir = "$env:TEMP\amnezia-v2-extract"

# Ensure directory
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    Write-Host "      Created directory $InstallDir..."
} else {
    Write-Host "      Already installed. Pulling latest files..." -ForegroundColor Yellow
}

try {
    Write-Host "      Downloading repository block directly from GitHub..."
    Invoke-WebRequest -Uri $ZipUrl -OutFile $TempZip -UseBasicParsing
    
    if (Test-Path $ExtractDir) { Remove-Item $ExtractDir -Recurse -Force }
    Write-Host "      Extracting files (no Git required)..."
    Expand-Archive -Path $TempZip -DestinationPath $ExtractDir -Force
    
    $SourceFolder = Join-Path $ExtractDir "amnezia-v2-deploy-main"
    Copy-Item -Path "$SourceFolder\*" -Destination $InstallDir -Recurse -Force
    
    # Cleanup
    Remove-Item $TempZip -Force
    Remove-Item $ExtractDir -Recurse -Force
    
    Write-Host "[✓] Files successfully applied." -ForegroundColor Green
} catch {
    Write-Host "[✗] Download or extraction failed. Check your internet." -ForegroundColor Red
    Read-Host "Press Enter to close this window..."
    return
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
$BatPath = "$InstallDir\amneziav2.bat"
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

