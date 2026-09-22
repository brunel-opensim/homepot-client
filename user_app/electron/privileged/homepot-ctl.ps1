# homepot-ctl.ps1 — Windows elevation helper for the HOMEPOT User App.
#
# Equivalent to the POSIX homepot-ctl shell script. Executes a fixed,
# allowlisted set of host operations with elevated privileges (restart/shutdown)
# and the owner-authorized free-form 'exec' op (script read from stdin).
#
# On Windows, this script is installed to C:\ProgramData\Homepot\homepot-ctl.ps1
# and registered as a scheduled task that runs with SYSTEM privileges.
# The agent invokes it directly (no sudo needed).
#
# Usage:
#   .\homepot-ctl.ps1 status
#   .\homepot-ctl.ps1 ensure-allowlist
#   .\homepot-ctl.ps1 run restart
#   .\homepot-ctl.ps1 run shutdown
#   .\homepot-ctl.ps1 run exec

param(
    [Parameter(Mandatory=$true, Position=0)]
    [ValidateSet("status", "ensure-allowlist", "run", "deprovision")]
    [string]$Verb,

    [Parameter(Position=1)]
    [string]$Operation
)

$ErrorActionPreference = "Stop"

# Paths
if ($env:HOMEPOT_ELEVATION_ROOT) {
    $Base = $env:HOMEPOT_ELEVATION_ROOT
} else {
    $Base = Join-Path $env:PROGRAMDATA "Homepot"
}
$Allowlist = Join-Path $Base "allowlist.json"
$Marker = Join-Path $Base "elevation_installed.marker"
$TaskName = "HOMEPOT-Elevation"

function Write-Status {
    $installed = Test-Path $PSCommandPath
    $provisioned = Test-Path $Marker
    $allowlistExists = Test-Path $Allowlist
    @{ installed = $installed; provisioned = $provisioned; allowlist = $allowlistExists } | ConvertTo-Json
}

function Test-AllowlistEntry {
    param([string]$Op)
    if (-not (Test-Path $Allowlist)) { return $false }
    $content = Get-Content $Allowlist -Raw
    return $content -match "op:$Op"
}

function Invoke-Run {
    param([string]$Op)

    # Check allowlist (fail-closed)
    if (-not (Test-AllowlistEntry -Op $Op)) {
        Write-Error "homepot-ctl: operation '$Op' is not allowed"
        exit 2
    }

    switch ($Op) {
        "restart" {
            shutdown /r /t 0
        }
        "shutdown" {
            shutdown /s /t 0
        }
        "exec" {
            # Read script from stdin and execute via PowerShell
            $script = [Console]::In.ReadToEnd()
            Invoke-Expression $script
        }
        default {
            Write-Error "homepot-ctl: operation '$Op' is not allowlisted"
            exit 2
        }
    }
}

function Install-Allowlist {
    # Ensure base directory exists
    if (-not (Test-Path $Base)) {
        New-Item -ItemType Directory -Path $Base -Force | Out-Null
    }

    # Write allowlist
    @"
op:restart
op:shutdown
op:exec
"@ | Set-Content -Path $Allowlist -Encoding UTF8

    # Create marker file
    "installed" | Set-Content -Path $Marker -Encoding UTF8

    # Register scheduled task that runs this script with SYSTEM privileges
    $scriptPath = $PSCommandPath
    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$scriptPath`" run"
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(5)
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -RunOnlyIfNetworkAvailable -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

    # Remove existing task if any
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Description "HOMEPOT Device Elevation Helper" | Out-Null
}

function Remove-Elevation {
    # Remove scheduled task
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

    # Remove marker and allowlist
    if (Test-Path $Marker) { Remove-Item $Marker -Force -ErrorAction SilentlyContinue }
    if (Test-Path $Allowlist) { Remove-Item $Allowlist -Force -ErrorAction SilentlyContinue }
}

# Main dispatch
switch ($Verb) {
    "status" { Write-Status }
    "ensure-allowlist" { Install-Allowlist }
    "run" {
        if (-not $Operation) {
            Write-Error "usage: homepot-ctl.ps1 run <operation>"
            exit 2
        }
        Invoke-Run -Op $Operation
    }
    "deprovision" { Remove-Elevation }
    default {
        Write-Error "usage: homepot-ctl.ps1 {status|ensure-allowlist|run <op>|deprovision}"
        exit 2
    }
}
