# Douyin Downloader Script
param(
    [string]$ConfigFile = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = (Get-Item $ScriptDir).Parent.FullName

# Use default config if not specified
if (-not $ConfigFile) {
    $ConfigFile = "$ProjectDir\config.yml"
} elseif (-not [System.IO.Path]::IsPathRooted($ConfigFile)) {
    # Convert relative path to absolute path
    $ConfigFile = Join-Path $ProjectDir $ConfigFile
}

# Check if config file exists
if (-not (Test-Path $ConfigFile)) {
    Write-Host "[ERROR] Config file not found: $ConfigFile" -ForegroundColor Red
    exit 1
}

# Get download path using Python
$downloadPath = python -c "
import yaml
with open(r'$ConfigFile', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)
print(config.get('path', ''))
"

$downloadPath = $downloadPath.Trim()

Write-Host ""
Write-Host "[CHECK] Download path: $downloadPath"

if (-not $downloadPath) {
    Write-Host "[ERROR] path not set in config.yml" -ForegroundColor Red
    exit 1
}

# Check if directory exists, create if not
if (-not (Test-Path $downloadPath)) {
    Write-Host "[CHECK] Directory not found, creating..."
    try {
        New-Item -ItemType Directory -Path $downloadPath -Force | Out-Null
        Write-Host "[OK] Directory created" -ForegroundColor Green
    } catch {
        Write-Host "[ERROR] Cannot create directory: $_" -ForegroundColor Red
        exit 1
    }
}

# Test if directory is writable
$testFile = Join-Path $downloadPath ".write_test_$(Get-Date -Format 'yyyyMMddHHmmss')"
try {
    [System.IO.File]::WriteAllText($testFile, "test")
    Remove-Item $testFile -Force
    Write-Host "[OK] Directory is writable" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Directory not writable: $downloadPath" -ForegroundColor Red
    Write-Host "[ERROR] Reason: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please check:" -ForegroundColor Yellow
    Write-Host "  1. Directory exists" -ForegroundColor Yellow
    Write-Host "  2. Current user has write permission" -ForegroundColor Yellow
    Write-Host "  3. Sandbox has access rule for this path" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Douyin Downloader" -ForegroundColor Cyan
Write-Host "  Config: $ConfigFile" -ForegroundColor DarkGray
Write-Host "========================================" -ForegroundColor Cyan

# Check Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "[ERROR] Python not found. Please install Python 3.9+" -ForegroundColor Red
    exit 1
}

# Change to project directory
Set-Location $ProjectDir

# Set UTF-8 encoding
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Run download
python run.py -c $ConfigFile --show-warnings
$exitCode = $LASTEXITCODE

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "=== Download Complete ===" -ForegroundColor Green
} else {
    Write-Host "=== Download Failed (code: $exitCode) ===" -ForegroundColor Yellow
}

Write-Host "Download directory: $downloadPath" -ForegroundColor DarkGray

