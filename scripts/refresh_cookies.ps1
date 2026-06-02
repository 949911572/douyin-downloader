# Refresh Douyin Cookies - opens browser for login, auto-updates config.yml
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PyScript = Join-Path $ScriptDir "_refresh_cookies.py"

Write-Host "Opening browser, please scan QR code to login..." -ForegroundColor Cyan

python "$PyScript"
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host "Cookie refresh succeeded" -ForegroundColor Green
} else {
    Write-Host "Cookie refresh failed or timed out" -ForegroundColor Yellow
}
pause
