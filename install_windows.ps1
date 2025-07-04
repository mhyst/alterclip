# Windows Install Script for AlterClip
# Run this script as Administrator

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Please run this script as Administrator" -ForegroundColor Red
    Exit 1
}

Write-Host "Installing AlterClip..." -ForegroundColor Green

# Get script directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptPath

# Create virtual environment
Write-Host "Creating virtual environment..." -ForegroundColor Green
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "Installing Python dependencies..." -ForegroundColor Green
pip install --upgrade pip
pip install -r requirements.txt

# Create scheduled task for main service
$mainAction = New-ScheduledTaskAction -Execute "$scriptPath\venv\Scripts\python.exe" -Argument "`"$scriptPath\alterclip.py`""
$mainTrigger = New-ScheduledTaskTrigger -AtStartup
$mainSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

# Create scheduled task for web service
$webAction = New-ScheduledTaskAction -Execute "$scriptPath\venv\Scripts\python.exe" -Argument "`"$scriptPath\web\app.py`""
$webTrigger = New-ScheduledTaskTrigger -AtStartup
$webSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

# Register the tasks
Register-ScheduledTask -TaskName "AlterClip" -Action $mainAction -Trigger $mainTrigger -Settings $mainSettings -RunLevel Highest -Force
Register-ScheduledTask -TaskName "AlterClip Web" -Action $webAction -Trigger $webTrigger -Settings $webSettings -RunLevel Highest -Force

# Start the services
Start-ScheduledTask -TaskName "AlterClip"
Start-ScheduledTask -TaskName "AlterClip Web"

Write-Host "`nInstallation complete!" -ForegroundColor Green
Write-Host "- AlterClip services are now running and will start automatically on system startup."
Write-Host "- Web interface is available at http://localhost:5000"
Write-Host "`nManagement commands:"
Write-Host "  Check status:      Get-ScheduledTask -TaskName 'AlterClip*' | Select-Object TaskName,State"
Write-Host "  Start services:    Start-ScheduledTask -TaskName 'AlterClip'; Start-ScheduledTask -TaskName 'AlterClip Web'"
Write-Host "  Stop services:     Stop-ScheduledTask -TaskName 'AlterClip*'"
Write-Host "  View in Task Scheduler: taskschd.msc"

# Keep the window open
Write-Host "`nPress any key to exit..."
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
