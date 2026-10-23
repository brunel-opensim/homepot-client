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
    [ValidateSet("status", "ensure-allowlist", "run", "execute-request", "deprovision")]
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

function Write-JsonFile {
    # Write UTF-8 *without* a BOM. Windows PowerShell's `Set-Content -Encoding
    # UTF8` emits a BOM, and a BOM-prefixed document is not valid JSON, so the
    # agent's parser rejected the result and reported an empty failure.
    param([string]$Path, $Data)
    $json = ConvertTo-Json -InputObject $Data
    [System.IO.File]::WriteAllText($Path, $json, (New-Object System.Text.UTF8Encoding($false)))
}

function Write-HelperError {
    # The agent reads this file when a request times out, so a failure inside
    # the helper is visible instead of looking like a silent hang.
    param([string]$Message)
    try {
        $Message | Set-Content -Path (Join-Path $Base "elevation_helper_error.txt") -Encoding UTF8
    } catch {
        # Reporting must never mask the original error.
    }
}

function Register-ElevationTask {
    # Register (or re-register) the SYSTEM scheduled task that executes
    # elevation requests. Verification matters: a task that failed to register
    # looks identical to a working one from the caller's point of view.
    param([string]$ScriptPath)

    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$ScriptPath`" execute-request"
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddYears(100)
    # No network gate: this is a purely local task and must run whether or not
    # the machine currently has a usable network profile. `StartWhenAvailable`
    # is deliberately not set — with a far-future trigger it only risks the
    # task firing once on its own right after registration.
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Description "HOMEPOT Device Elevation Helper" | Out-Null

    # Verify the task really exists and runs the `execute-request` verb. The
    # Task Scheduler API is used rather than `schtasks /xml` because the XML
    # output is UTF-16 and would not survive decoding reliably.
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
    # is current. Idempotent: re-registering must not duplicate the ACE. Uses
    # the Task Scheduler COM API (`Schedule.Service`) — the only supported way
    # to edit a task's security descriptor.
    $scheduler = New-Object -ComObject Schedule.Service
    $scheduler.Connect()
    $registered = $scheduler.GetFolder("\").GetTask($TaskName)
    $sddl = $registered.GetSecurityDescriptor(0xF)   # 0xF = owner|group|dacl|sacl
    if ($sddl -notmatch '\(A;;GRGX;;;AU\)') {
        $sddl = $sddl + '(A;;GRGX;;;AU)'
        $registered.SetSecurityDescriptor($sddl, 0xF)
    }
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

    # Register scheduled task that runs this script with SYSTEM privileges.
    # The action is `execute-request`: the unprivileged agent writes a request
    # file and triggers the task via `schtasks /run`; this SYSTEM context then
    # reads and executes it. The trigger is far-future so the task never fires
    # on its own.
    Register-ElevationTask -ScriptPath $PSCommandPath

    # Create marker file — only after the task is verified.
    "installed" | Set-Content -Path $Marker -Encoding UTF8
}

function Remove-Elevation {
    # Remove scheduled task
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

    # Remove marker and allowlist
    if (Test-Path $Marker) { Remove-Item $Marker -Force -ErrorAction SilentlyContinue }
    if (Test-Path $Allowlist) { Remove-Item $Allowlist -Force -ErrorAction SilentlyContinue }
}

function Invoke-ExecuteRequest {
    # Read a request file written by the unprivileged agent and execute it as
    # SYSTEM (this helper runs via the HOMEPOT-Elevation scheduled task), then
    # write a result file the agent polls for. This is the Windows equivalent
    # of `sudo -n homepot-ctl run <op>`: the agent never receives blanket
    # elevation, and each operation is read from a file it can write but not
    # (directly) execute elevated.
    $RequestPath = Join-Path $Base "elevation-request.json"
    # Clear the previous attempt's error first so the file always describes
    # the most recent run.
    Remove-Item (Join-Path $Base "elevation_helper_error.txt") -Force -ErrorAction SilentlyContinue

    if (-not (Test-Path $RequestPath)) {
        Write-HelperError -Message "no elevation request pending"
        [Console]::Error.WriteLine("homepot-ctl: no elevation request pending")
        exit 2
    }

    try {
        $req = Get-Content $RequestPath -Raw | ConvertFrom-Json
    } catch {
        Write-HelperError -Message "could not parse the elevation request: $($_.Exception.Message)"
        [Console]::Error.WriteLine("homepot-ctl: could not parse the elevation request")
        exit 2
    }

    $reqId = $req.request_id
    $ResultPath = Join-Path $Base "elevation-result-$reqId.json"

    $stdout = ""
    $stderr = ""
    $exitCode = 0

    try {
        switch ($req.op) {
            "exec" {
                # Allowlist gate (fail-closed): free-form exec is only honoured when
                # the owner has explicitly allowed it.
                if (-not (Test-AllowlistEntry -Op "exec")) {
                    $stderr = "homepot-ctl: operation 'exec' is not allowed"
                    $exitCode = 2
                    break
                }
                try {
                    $scriptBlock = [scriptblock]::Create([string]$req.script)
                    $stdout = (& $scriptBlock 2>&1 | Out-String)
                    $exitCode = 0
                } catch {
                    $stderr = $_.Exception.Message
                    $exitCode = 1
                }
            }
            "restart" {
                if (-not (Test-AllowlistEntry -Op "restart")) {
                    $stderr = "homepot-ctl: operation 'restart' is not allowed"
                    $exitCode = 2
                    break
                }
                $stdout = "restart initiated"
                shutdown /r /t 5
            }
            "shutdown" {
                if (-not (Test-AllowlistEntry -Op "shutdown")) {
                    $stderr = "homepot-ctl: operation 'shutdown' is not allowed"
                    $exitCode = 2
                    break
                }
                $stdout = "shutdown initiated"
                shutdown /s /t 5
            }
            default {
                $stderr = "homepot-ctl: unknown elevation op '$($req.op)'"
                $exitCode = 2
            }
        }
    } catch {
        $stderr = $_.Exception.Message
        $exitCode = 1
    }

    if ($exitCode -ne 0) {
        Write-HelperError -Message $stderr
    }

    Write-JsonFile -Path $ResultPath -Data @{
        request_id = $reqId
        exit_code  = $exitCode
        stdout     = $stdout
        stderr     = $stderr
    }

    # Best-effort cleanup of the consumed request.
    Remove-Item $RequestPath -Force -ErrorAction SilentlyContinue
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
    "execute-request" { Invoke-ExecuteRequest }
    "deprovision" { Remove-Elevation }
    default {
        Write-Error "usage: homepot-ctl.ps1 {status|ensure-allowlist|run <op>|execute-request|deprovision}"
        exit 2
    }
}
