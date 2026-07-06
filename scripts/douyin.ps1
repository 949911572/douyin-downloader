# Douyin Downloader - Unified CLI Entry
param(
    [string]$Action = "download",
    [string]$ConfigFile = "",
    [string[]]$Url = @(),
    [int]$Thread = 0,
    [string]$Path = "",
    [string]$MarkAwemeId = "",
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = (Get-Item $ScriptDir).Parent.FullName

$VALID_ACTIONS = @("download", "retry-failed", "list-failed", "mark-all-failed-skipped", "mark-skipped", "backup-db", "verify-login", "refresh-cookies", "fetch-links", "help")

if (-not $VALID_ACTIONS.Contains($Action)) {
    Write-Host "[ERROR] Invalid action: $Action" -ForegroundColor Red
    Write-Host "Valid actions: $($VALID_ACTIONS -join ', ')" -ForegroundColor Yellow
    exit 1
}

if ($Action -eq "help") {
    Write-Host ""
    Write-Host "=========================================" -ForegroundColor Cyan
    Write-Host "  Douyin Downloader - Help" -ForegroundColor Cyan
    Write-Host "=========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage: .\scripts\douyin.ps1 -Action <action> [parameters]" -ForegroundColor White
    Write-Host ""
    Write-Host "Actions:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  download              Incremental download (default)" -ForegroundColor White
    Write-Host "    Params: -ConfigFile, -Url, -Thread, -Path, -Verbose" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  retry-failed          Retry all failed videos" -ForegroundColor White
    Write-Host "    Params: -ConfigFile" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  list-failed           List all failed videos" -ForegroundColor White
    Write-Host "    Params: -ConfigFile" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  mark-all-failed-skipped  Mark all failed videos as skipped" -ForegroundColor White
    Write-Host "    Params: -ConfigFile" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  mark-skipped          Mark single video as skipped" -ForegroundColor White
    Write-Host "    Params: -MarkAwemeId, -ConfigFile" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  backup-db             Backup database to data/db_backup/" -ForegroundColor White
    Write-Host ""
    Write-Host "  verify-login          Verify login status via browser (manual)" -ForegroundColor White
    Write-Host ""
    Write-Host "  refresh-cookies       Refresh cookies from chrome_user_data" -ForegroundColor White
    Write-Host ""
    Write-Host "  fetch-links           Fetch links via browser (favorites or user homepage)" -ForegroundColor White
    Write-Host "    Params: -Url (optional, for user homepage scanning)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  help                  Show this help" -ForegroundColor White
    Write-Host ""
    Write-Host "Common Params:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  -ConfigFile path      Specify config file (default: config.yml)" -ForegroundColor White
    Write-Host "  -Url url              Add download URL (can specify multiple times)" -ForegroundColor White
    Write-Host "  -Thread number        Specify thread count" -ForegroundColor White
    Write-Host "  -Path path            Specify download directory" -ForegroundColor White
    Write-Host "  -Verbose              Show verbose logs" -ForegroundColor White
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  .\scripts\douyin.ps1" -ForegroundColor White
    Write-Host "  .\scripts\douyin.ps1 -Action download -ConfigFile config_temp.yml" -ForegroundColor White
    Write-Host "  .\scripts\douyin.ps1 -Action download -Url https://v.douyin.com/xxx/" -ForegroundColor White
    Write-Host "  .\scripts\douyin.ps1 -Action retry-failed" -ForegroundColor White
    Write-Host "  .\scripts\douyin.ps1 -Action list-failed" -ForegroundColor White
    Write-Host "  .\scripts\douyin.ps1 -Action mark-all-failed-skipped" -ForegroundColor White
    Write-Host "  .\scripts\douyin.ps1 -Action mark-skipped -MarkAwemeId 7656278130479029862" -ForegroundColor White
    Write-Host "  .\scripts\douyin.ps1 -Action backup-db" -ForegroundColor White
    Write-Host "  .\scripts\douyin.ps1 -Action verify-login" -ForegroundColor White
    Write-Host "  .\scripts\douyin.ps1 -Action refresh-cookies" -ForegroundColor White
    Write-Host ""
    exit 0
}

if (-not $ConfigFile) {
    $ConfigFile = "$ProjectDir\config.yml"
} elseif (-not [System.IO.Path]::IsPathRooted($ConfigFile)) {
    $ConfigFile = Join-Path $ProjectDir $ConfigFile
}

if (-not (Test-Path $ConfigFile)) {
    Write-Host "[ERROR] Config file not found: $ConfigFile" -ForegroundColor Red
    exit 1
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "[ERROR] Python not found. Please install Python 3.9+" -ForegroundColor Red
    exit 1
}

Set-Location $ProjectDir
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:DOUYIN_DOWNLOADER_LAUNCHED_BY_PS1 = 'true'



function Build-DownloadArgs {
    param(
        [string]$configFile,
        [string[]]$urls,
        [int]$thread,
        [string]$path,
        [switch]$verbose
    )
    
    $args = @("-c", $configFile)
    
    if ($urls -and $urls.Count -gt 0) {
        foreach ($u in $urls) {
            $args += @("-u", $u)
        }
    }
    
    if ($thread -gt 0) {
        $args += @("-t", $thread)
    }
    
    if ($path) {
        $args += @("-p", $path)
    }
    
    if ($verbose) {
        $args += @("-v")
    } else {
        $args += @("--show-warnings")
    }
    
    return $args
}

switch ($Action) {
    "verify-login" {
        Write-Host ""
        Write-Host "=========================================" -ForegroundColor Cyan
        Write-Host "  Verify Login Status via Browser" -ForegroundColor Cyan
        Write-Host "=========================================" -ForegroundColor Cyan
        Write-Host ""
        python scripts/verify_login.py
        $exitCode = $LASTEXITCODE
        Write-Host ""
        if ($exitCode -eq 0) {
            Write-Host "=== Verify Complete ===" -ForegroundColor Green
        } else {
            Write-Host "=== Verify Failed (code: $exitCode) ===" -ForegroundColor Yellow
        }
        exit $exitCode
    }

    "refresh-cookies" {
        Write-Host ""
        Write-Host "=========================================" -ForegroundColor Cyan
        Write-Host "  Refresh Cookies" -ForegroundColor Cyan
        Write-Host "=========================================" -ForegroundColor Cyan
        Write-Host ""
        python scripts/_refresh_cookies.py
        $exitCode = $LASTEXITCODE
        Write-Host ""
        if ($exitCode -eq 0) {
            Write-Host "=== Refresh Complete ===" -ForegroundColor Green
        } else {
            Write-Host "=== Refresh Failed (code: $exitCode) ===" -ForegroundColor Yellow
        }
        exit $exitCode
    }

    "fetch-links" {
        Write-Host ""
        Write-Host "=========================================" -ForegroundColor Cyan
        Write-Host "  Fetch Links" -ForegroundColor Cyan
        Write-Host "=========================================" -ForegroundColor Cyan
        Write-Host ""
        if ($Url) {
            Write-Host "  目标地址: $Url"
            Write-Host ""
            python scripts/fetch_links.py "$Url"
        } else {
            python scripts/fetch_links.py
        }
        $exitCode = $LASTEXITCODE
        Write-Host ""
        if ($exitCode -eq 0) {
            Write-Host "=== Fetch Complete ===" -ForegroundColor Green
        } else {
            Write-Host "=== Fetch Failed (code: $exitCode) ===" -ForegroundColor Yellow
        }
        exit $exitCode
    }

    "list-failed" {
        Write-Host ""
        Write-Host "=========================================" -ForegroundColor Cyan
        Write-Host "  List Failed Videos" -ForegroundColor Cyan
        Write-Host "=========================================" -ForegroundColor Cyan
        Write-Host ""
        python run.py -c $ConfigFile --list-failed
        exit $LASTEXITCODE
    }

    "mark-all-failed-skipped" {
        Write-Host ""
        Write-Host "=========================================" -ForegroundColor Cyan
        Write-Host "  Mark All Failed Videos as Skipped" -ForegroundColor Cyan
        Write-Host "  Config: $ConfigFile" -ForegroundColor DarkGray
        Write-Host "=========================================" -ForegroundColor Cyan
        Write-Host ""
        python run.py -c $ConfigFile --mark-all-failed-skipped
        $exitCode = $LASTEXITCODE
        Write-Host ""
        if ($exitCode -eq 0) {
            Write-Host "=== Mark Complete ===" -ForegroundColor Green
        } else {
            Write-Host "=== Mark Failed (code: $exitCode) ===" -ForegroundColor Yellow
        }
        exit $exitCode
    }

    "mark-skipped" {
        if (-not $MarkAwemeId) {
            Write-Host "[ERROR] -MarkAwemeId is required for mark-skipped action" -ForegroundColor Red
            Write-Host "Usage: .\scripts\douyin.ps1 -Action mark-skipped -MarkAwemeId <aweme_id>" -ForegroundColor Yellow
            exit 1
        }
        
        Write-Host ""
        Write-Host "=========================================" -ForegroundColor Cyan
        Write-Host "  Mark Video as Skipped" -ForegroundColor Cyan
        Write-Host "  Aweme ID: $MarkAwemeId" -ForegroundColor DarkGray
        Write-Host "=========================================" -ForegroundColor Cyan
        Write-Host ""
        python run.py -c $ConfigFile --mark-skipped $MarkAwemeId
        $exitCode = $LASTEXITCODE
        Write-Host ""
        if ($exitCode -eq 0) {
            Write-Host "=== Mark Complete ===" -ForegroundColor Green
        } else {
            Write-Host "=== Mark Failed (code: $exitCode) ===" -ForegroundColor Yellow
        }
        exit $exitCode
    }

    "backup-db" {
        $dbFile = Join-Path $ProjectDir "dy_downloader.db"
        $backupDir = Join-Path $ProjectDir "data\db_backup"

        Write-Host ""
        Write-Host "=========================================" -ForegroundColor Cyan
        Write-Host "  Backup Database" -ForegroundColor Cyan
        Write-Host "=========================================" -ForegroundColor Cyan
        Write-Host ""

        if (-not (Test-Path $dbFile)) {
            Write-Host "[ERROR] Database not found: $dbFile" -ForegroundColor Red
            exit 1
        }

        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $targetDir = Join-Path $backupDir $timestamp
        $targetFile = Join-Path $targetDir "dy_downloader.db"

        try {
            New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
            Copy-Item -Path $dbFile -Destination $targetFile -Force
            $fileSize = (Get-Item $targetFile).Length
            $sizeKB = [math]::Round($fileSize / 1KB, 1)
            Write-Host "[OK] Backup complete" -ForegroundColor Green
            Write-Host "  Source: $dbFile" -ForegroundColor DarkGray
            Write-Host "  Target: $targetFile" -ForegroundColor DarkGray
            Write-Host "  Size:   $sizeKB KB" -ForegroundColor DarkGray
        } catch {
            Write-Host "[ERROR] Backup failed: $_" -ForegroundColor Red
            exit 1
        }
        exit 0
    }

    "retry-failed" {
        Write-Host ""
        Write-Host "=========================================" -ForegroundColor Cyan
        Write-Host "  Retry Failed Videos" -ForegroundColor Cyan
        Write-Host "  Config: $ConfigFile" -ForegroundColor DarkGray
        Write-Host "=========================================" -ForegroundColor Cyan
        Write-Host ""
        python run.py -c $ConfigFile --retry-failed
        $exitCode = $LASTEXITCODE
        
        Write-Host ""
        if ($exitCode -eq 0) {
            Write-Host "=== Retry Complete ===" -ForegroundColor Green
        } else {
            Write-Host "=== Retry Failed (code: $exitCode) ===" -ForegroundColor Yellow
        }
        exit $exitCode
    }

    "download" {
        $downloadPath = python -c "
import yaml
with open(r'$ConfigFile', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)
print(config.get('path', ''))
"
        $downloadPath = $downloadPath.Trim()

        Write-Host ""
        Write-Host "[CHECK] Download path from config: $downloadPath"

        if (-not [System.IO.Path]::IsPathRooted($downloadPath)) {
            $downloadPath = Join-Path $ProjectDir $downloadPath
            Write-Host "[CHECK] Resolved absolute path: $downloadPath"
        }

        if (-not $downloadPath) {
            Write-Host "[ERROR] path not set in config.yml" -ForegroundColor Red
            exit 1
        }

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
            exit 1
        }

        Write-Host ""
        Write-Host "[CHECK] Validating cookies..."
        python scripts/check_cookies.py "$ConfigFile"
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] Cookie validation failed. Please check and refresh cookies." -ForegroundColor Red
            exit 1
        }

        Write-Host ""
        Write-Host "=========================================" -ForegroundColor Cyan
        Write-Host "  Douyin Downloader" -ForegroundColor Cyan
        Write-Host "  Config: $ConfigFile" -ForegroundColor DarkGray
        Write-Host "=========================================" -ForegroundColor Cyan
        Write-Host ""
        $downloadArgs = Build-DownloadArgs -configFile $ConfigFile -urls $Url -thread $Thread -path $Path -verbose $Verbose
        python run.py @downloadArgs
        $exitCode = $LASTEXITCODE

        Write-Host ""
        if ($exitCode -eq 0) {
            Write-Host "=== Download Complete ===" -ForegroundColor Green
        } else {
            Write-Host "=== Download Failed (code: $exitCode) ===" -ForegroundColor Yellow
        }
        Write-Host "Download directory: $downloadPath" -ForegroundColor DarkGray
        exit $exitCode
    }
}