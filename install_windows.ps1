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

# Create scheduled task to run on startup
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -Command `"& '$scriptPath\venv\Scripts\python.exe' '$scriptPath\alterclip.py' --web`"
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

# Register the task
Register-ScheduledTask -TaskName "AlterClip" -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest -Force

# Start the service
Start-ScheduledTask -TaskName "AlterClip"

Write-Host "`nInstallation complete!" -ForegroundColor Green
Write-Host "AlterClip is now running and will start automatically on system startup."
Write-Host "You can access the web interface at http://localhost:5000"
Write-Host "To manage the service, use Task Scheduler (search for 'Task Scheduler' in Start menu)"

# Keep the window open
Write-Host "`nPress any key to exit..."
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
