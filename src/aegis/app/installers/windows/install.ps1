# Aegis AI Threat Monitor - Windows Installer
# Run this script in PowerShell
#
# Usage:
#   Set-ExecutionPolicy Bypass -Scope Process -Force
#   .\install.ps1

param(
    [switch]$Uninstall,
    [ValidateRange(1024, 65535)]
    [int]$Port = 8741
)

$ErrorActionPreference = "Stop"
$AppName = "Aegis"
$ServiceName = "AegisMonitor"
$TaskName = "AegisStartup"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Aegis AI Threat Monitor" -ForegroundColor Cyan
Write-Host "  Windows Installer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Security: Validate port is in valid range
if ($Port -lt 1024 -or $Port -gt 65535) {
    Write-Host "  ERROR: Port must be between 1024 and 65535" -ForegroundColor Red
    exit 1
}

function Install-Aegis {
    Write-Host "[1/5] Checking Python installation..." -ForegroundColor Yellow

    try {
        $pythonVersion = python --version 2>&1
        Write-Host "  Found: $pythonVersion" -ForegroundColor Green
    } catch {
        Write-Host "  ERROR: Python not found. Please install Python 3.9+ from python.org" -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "[2/5] Installing Aegis via pip..." -ForegroundColor Yellow

    try {
        pip install --upgrade ai-aegis[app]
        Write-Host "  Aegis installed successfully!" -ForegroundColor Green
    } catch {
        Write-Host "  ERROR: Failed to install Aegis: $_" -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "[3/5] Creating startup script..." -ForegroundColor Yellow

    $AppDataDir = "$env:LOCALAPPDATA\Aegis"
    if (-not (Test-Path $AppDataDir)) {
        New-Item -ItemType Directory -Path $AppDataDir -Force | Out-Null
    }

    # Security: Use validated port value
    $ValidatedPort = [int]$Port
    $StartupScript = @"
# Aegis Startup Script
`$port = $ValidatedPort
Start-Process -WindowStyle Hidden -FilePath "python" -ArgumentList "-m", "aegis.app", "--port", "`$port"
"@

    $ScriptPath = "$AppDataDir\start-aegis.ps1"
    $StartupScript | Out-File -FilePath $ScriptPath -Encoding UTF8

    # Security: Set restrictive permissions on script
    $acl = Get-Acl $ScriptPath
    $acl.SetAccessRuleProtection($true, $false)
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($env:USERNAME, "FullControl", "Allow")
    $acl.SetAccessRule($rule)
    Set-Acl $ScriptPath $acl

    Write-Host "  Created: $ScriptPath" -ForegroundColor Green

    Write-Host ""
    Write-Host "[4/5] Creating Windows Scheduled Task for autostart..." -ForegroundColor Yellow

    # Remove existing task if present
    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }

    $Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$ScriptPath`""
    $Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    $Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Description "Aegis AI Threat Monitor - Local API Server"
    Write-Host "  Scheduled task created: $TaskName" -ForegroundColor Green

    Write-Host ""
    Write-Host "[5/5] Starting Aegis..." -ForegroundColor Yellow

    Start-Process -WindowStyle Hidden -FilePath "powershell.exe" -ArgumentList "-ExecutionPolicy Bypass -File `"$ScriptPath`""
    Start-Sleep -Seconds 3

    # Verify it's running
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$ValidatedPort/health" -UseBasicParsing -TimeoutSec 5
        Write-Host "  Aegis is running on port $ValidatedPort" -ForegroundColor Green
    } catch {
        Write-Host "  Aegis started (health check pending)" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Installation Complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Aegis is now running in the background." -ForegroundColor White
    Write-Host ""
    Write-Host "API Endpoint: http://localhost:$ValidatedPort/analyze" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To open the desktop app:" -ForegroundColor White
    Write-Host "  aegis-app" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To uninstall:" -ForegroundColor White
    Write-Host "  .\install.ps1 -Uninstall" -ForegroundColor Yellow
    Write-Host ""
}

function Uninstall-Aegis {
    Write-Host "Uninstalling Aegis..." -ForegroundColor Yellow
    Write-Host ""

    # Stop running processes
    Write-Host "[1/4] Stopping Aegis processes..." -ForegroundColor Yellow
    Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -like "*aegis*"
    } | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "  Done" -ForegroundColor Green

    # Remove scheduled task
    Write-Host "[2/4] Removing scheduled task..." -ForegroundColor Yellow
    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "  Removed: $TaskName" -ForegroundColor Green
    } else {
        Write-Host "  No task found" -ForegroundColor Gray
    }

    # Remove app data
    Write-Host "[3/4] Removing app data..." -ForegroundColor Yellow
    $AppDataDir = "$env:LOCALAPPDATA\Aegis"
    if (Test-Path $AppDataDir) {
        Remove-Item -Path $AppDataDir -Recurse -Force
        Write-Host "  Removed: $AppDataDir" -ForegroundColor Green
    } else {
        Write-Host "  No app data found" -ForegroundColor Gray
    }

    # Uninstall pip package
    Write-Host "[4/4] Uninstalling pip package..." -ForegroundColor Yellow
    pip uninstall ai-aegis -y 2>&1 | Out-Null
    Write-Host "  Done" -ForegroundColor Green

    Write-Host ""
    Write-Host "Aegis has been uninstalled." -ForegroundColor Green
    Write-Host ""
}

# Main
if ($Uninstall) {
    Uninstall-Aegis
} else {
    Install-Aegis
}
