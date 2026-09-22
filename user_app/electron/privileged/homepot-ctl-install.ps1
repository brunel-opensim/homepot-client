# homepot-ctl-install.ps1 — one-time OS elevation install for the HOMEPOT User App (Windows).
#
# Run through a UAC admin prompt so it executes with elevated privileges.
# It installs the scoped homepot-ctl.ps1 helper and registers a scheduled task
# that runs with SYSTEM privileges for elevated operations.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File homepot-ctl-install.ps1 [-CtlPath <source>] [-Root <target>]

param(
    [Parameter(Mandatory=$true)]
    [string]$CtlPath,

    [string]$Root
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $CtlPath)) {
    Write-Error "homepot-ctl-install: --CtlPath <source> is required and must exist"
    exit 2
}

if ($Root) {
    $InstallDir = $Root
} else {
    $InstallDir = Join-Path $env:PROGRAMDATA "Homepot"
}

$TaskName = "HOMEPOT-Elevation"

# Create install directory
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

# Copy the helper script
$destPath = Join-Path $InstallDir "homepot-ctl.ps1"
Copy-Item -Path $CtlPath -Destination $destPath -Force

# Create allowlist
$allowlistPath = Join-Path $InstallDir "allowlist.json"
@"
op:restart
op:shutdown
op:exec
"@ | Set-Content -Path $allowlistPath -Encoding UTF8

# Create marker file
$markerPath = Join-Path $InstallDir "elevation_installed.marker"
"installed" | Set-Content -Path $markerPath -Encoding UTF8

# Register scheduled task that runs the helper with SYSTEM privileges
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$destPath`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(5)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -RunOnlyIfNetworkAvailable -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# Remove existing task if any
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Description "HOMEPOT Device Elevation Helper" | Out-Null

Write-Output "homepot-ctl installed successfully to $destPath"
Write-Output "Scheduled task '$TaskName' registered with SYSTEM privileges"
