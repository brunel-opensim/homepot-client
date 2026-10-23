# homepot-ctl-install.ps1 — one-time OS elevation install for the HOMEPOT User App (Windows).
#
# Run through a UAC admin prompt so it executes with elevated privileges.
# It installs the scoped homepot-ctl.ps1 helper and registers a scheduled task
# that runs with SYSTEM privileges for elevated operations.
#
# The scheduled task is registered *and verified* before the "installed" marker
# is written. Writing the marker first made a failed task registration look
# like a successful install: the User App reported the grant as working, the
# agent then timed out waiting for a helper that was never scheduled, and
# nothing in the UI said why.
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
    [Console]::Error.WriteLine("homepot-ctl-install: --CtlPath <source> is required and must exist")
    exit 2
}

if ($Root) {
    $InstallDir = $Root
} else {
    $InstallDir = Join-Path $env:PROGRAMDATA "Homepot"
}

$TaskName = "HOMEPOT-Elevation"
$destPath = Join-Path $InstallDir "homepot-ctl.ps1"
$allowlistPath = Join-Path $InstallDir "allowlist.json"
$markerPath = Join-Path $InstallDir "elevation_installed.marker"
$statusPath = Join-Path $InstallDir "elevation_install_status.txt"

# Create install directory
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

# The installer always reports its outcome through this file: the User App
# starts it via ShellExecute (UAC), which cannot capture stdout/stderr.
Remove-Item $statusPath -Force -ErrorAction SilentlyContinue

try {
    # Copy the helper script
    Copy-Item -Path $CtlPath -Destination $destPath -Force

    # Register scheduled task that runs the helper with SYSTEM privileges. The
    # action is `execute-request` (the unprivileged agent writes a request file
    # and triggers the task via `schtasks /run`); the trigger is far-future so
    # the task never fires on its own.
    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$destPath`" execute-request"
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddYears(100)
    # No network gate: this is a purely local task and must run whether or not
    # the machine currently has a usable network profile. `StartWhenAvailable`
    # is deliberately not set — with a far-future trigger it only risks the
    # task firing once on its own right after registration.
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

    # Remove existing task if any
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Description "HOMEPOT Device Elevation Helper" | Out-Null

    # Verify the task really exists and runs the `execute-request` verb before
    # declaring success. The Task Scheduler API is used rather than
    # `schtasks /xml` because the XML output is UTF-16 and would not survive
    # decoding reliably.
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    $arguments = ($task.Actions | ForEach-Object { $_.Arguments }) -join " "
    if ($arguments -notmatch "execute-request") {
        throw "scheduled task '$TaskName' was registered with an unexpected action"
    }

    # Grant read+execute to Authenticated Users on the task so the unprivileged
    # agent can start it with `schtasks /run`. A task registered with a SYSTEM
    # principal gets a default DACL granting only Administrators and SYSTEM, so
    # the agent's `schtasks /run` fails with "Access is denied". The same grant
    # also lets the agent read the task back (`schtasks /query`) to confirm it
    # is current. Idempotent: re-running the installer must not duplicate the
    # ACE. Uses the Task Scheduler COM API (`Schedule.Service`) — the only
    # supported way to edit a task's security descriptor.
    $scheduler = New-Object -ComObject Schedule.Service
    $scheduler.Connect()
    $registered = $scheduler.GetFolder("\").GetTask($TaskName)
    $sddl = $registered.GetSecurityDescriptor(0xF)   # 0xF = owner|group|dacl|sacl
    if ($sddl -notmatch '\(A;;GRGX;;;AU\)') {
        $sddl = $sddl + '(A;;GRGX;;;AU)'
        $registered.SetSecurityDescriptor($sddl, 0xF)
    }

    # Create allowlist
    @"
op:restart
op:shutdown
op:exec
"@ | Set-Content -Path $allowlistPath -Encoding UTF8

    # Create marker file — only now is the elevation layer genuinely usable.
    "installed" | Set-Content -Path $markerPath -Encoding UTF8

    "ok" | Set-Content -Path $statusPath -Encoding UTF8
    Write-Output "homepot-ctl installed successfully to $destPath"
    Write-Output "Scheduled task '$TaskName' registered with SYSTEM privileges"
    exit 0
} catch {
    $message = $_.Exception.Message
    # Leave the layer uninstalled so a failed install never looks successful.
    Remove-Item $markerPath -Force -ErrorAction SilentlyContinue
    try {
        $message | Set-Content -Path $statusPath -Encoding UTF8
    } catch {
        # Reporting the failure must never mask the original error.
    }
    [Console]::Error.WriteLine("homepot-ctl-install: $message")
    exit 1
}
