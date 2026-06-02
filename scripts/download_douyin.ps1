# 抖音下载 - douyin-downloader 一键启动脚本
# 使用 config.yml 中的配置批量下载

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = (Get-Item $ScriptDir).Parent.FullName
$ConfigFile = "$ProjectDir\config.yml"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  抖音批量下载器 douyin-downloader" -ForegroundColor Cyan
Write-Host "  配置: $ConfigFile" -ForegroundColor DarkGray
Write-Host "========================================" -ForegroundColor Cyan

# 检查 Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "[ERROR] Python not found. Please install Python 3.9+" -ForegroundColor Red
    pause
    exit 1
}

# 切换到项目目录
Set-Location $ProjectDir

# 运行下载
python run.py -c $ConfigFile --show-warnings
$exitCode = $LASTEXITCODE

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "=== 下载完成 ===" -ForegroundColor Green
} else {
    Write-Host "=== 下载异常退出 (code: $exitCode) ===" -ForegroundColor Yellow
}

# 打开下载目录
$downloadPath = (Get-Content $ConfigFile -Raw | ConvertFrom-Yaml).path
if ($downloadPath) {
    Write-Host "下载目录: $downloadPath" -ForegroundColor DarkGray
    explorer $downloadPath
}

pause
