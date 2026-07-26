<#
.SYNOPSIS
    Performs an atomic in-place upgrade of the HOMEPOT Device Agent.

.DESCRIPTION
    This script:
      - Stops the HomepotAgent Windows service.
      - Upgrades the homepot-client[agent] Python package via pip.
      - Re-registers the service (in case the wrapper changed).
      - Restarts the service.

    If any step fails the script exits with a non-zero exit code and
    the service is left in a consistent state (stopped, not broken).

.PARAMETER PythonPath
    Path to the Python executable.  Defaults to the python.exe used by
    the currently installed service.

.PARAMETER Source
    Optional path to a local wheel or source directory.  When set, pip
    installs from this path instead of PyPI (useful for testing pre-release
    builds).

.EXAMPLE
    .\upgrade-agent.ps1
    .\upgrade-agent.ps1 -PythonPath "C:\Python311\python.exe"
    .\upgrade-agent.ps1 -Source "C:\dist\homepot_client-0.2.0-py3-none-any.whl"
#>

param(
    [string]$PythonPath = "",
    [string]$Source = ""
)

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

function Find-Python {
    <#
    .SYNOPSIS
        Locate a suitable Python 3.11+ executable.
    #>
    if ($PythonPath -and (Test-Path $PythonPath)) {
        return $PythonPath
    }
    # Try the path registered in the service first
    $service = Get-CimInstance -ClassName Win32_Service -Filter "Name='HomepotAgent'" -ErrorAction SilentlyContinue
    if ($service -and $service.PathName) {
        # PathName looks like: "C:\Python311\python.exe C:\...\homepot_agent_service.py"
        $parts = $service.PathName -split '\.exe '
        if ($parts[0]) {
            $candidate = $parts[0] + ".exe"
            if (Test-Path $candidate) { return $candidate }
        }
    }
    foreach ($candidate in @("python3.exe", "python.exe")) {
        $exe = (Get-Command $candidate -ErrorAction SilentlyContinue).Source
        if ($exe) { return $exe }
    }
    $common = @(
        "$env:ProgramFiles\Python311\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "${env:ProgramFiles(x86)}\Python311\python.exe",
        "${env:ProgramFiles(x86)}\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
    )
    foreach ($path in $common) {
        if (Test-Path $path) { return $path }
    }
    return $null
}

function Test-Admin {
    <#
    .SYNOPSIS
        Return $true if the script is running as Administrator.
    #>
    $id = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object System.Security.Principal.WindowsPrincipal($id)
    return $principal.IsInRole(
        [System.Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

function Get-ServiceScript {
    <#
    .SYNOPSIS
        Return the full path to homepot_agent_service.py.
    #>
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
    return Join-Path $scriptDir "homepot_agent_service.py"
}

# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------

if (-not (Test-Admin)) {
    Write-Error "Administrator privileges required.  Restart as Administrator."
    exit 1
}

$python = Find-Python
if (-not $python) {
    Write-Error "Python 3.11+ not found."
    exit 1
}
Write-Host "Using Python: $python"

$serviceScript = Get-ServiceScript
if (-not (Test-Path $serviceScript)) {
    Write-Error "Service wrapper not found: $serviceScript"
    exit 1
}

# ---------------------------------------------------------------------------
# Phase 1: Stop the service
# ---------------------------------------------------------------------------

Write-Host "Phase 1/4: Stopping HomepotAgent service..."
$service = Get-Service -Name "HomepotAgent" -ErrorAction SilentlyContinue
if ($service -and $service.Status -eq "Running") {
    & $python $serviceScript stop
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Service stop returned exit code $LASTEXITCODE; continuing..."
    }
    Start-Sleep -Seconds 3
} else {
    Write-Host "  Service is not running."
}

# ---------------------------------------------------------------------------
# Phase 2: Upgrade the package
# ---------------------------------------------------------------------------

Write-Host "Phase 2/4: Upgrading homepot-client[agent]..."
if ($Source) {
    $pipArgs = @("-m", "pip", "install", "--upgrade", $Source)
} else {
    $pipArgs = @("-m", "pip", "install", "--upgrade", "homepot-client[agent]")
}
$process = Start-Process -FilePath $python -ArgumentList $pipArgs -NoNewWindow -Wait -PassThru
if ($process.ExitCode -ne 0) {
    Write-Error "pip upgrade failed (exit code: $($process.ExitCode))."
    Write-Error "Service is stopped and will NOT be restarted."
    exit 1
}
Write-Host "  Package upgraded."

# ---------------------------------------------------------------------------
# Phase 3: Re-register the service
# ---------------------------------------------------------------------------

Write-Host "Phase 3/4: Re-registering service..."
& $python $serviceScript remove | Out-Null
Start-Sleep -Seconds 1
& $python $serviceScript install
if ($LASTEXITCODE -ne 0) {
    Write-Error "Service re-registration failed (exit code: $LASTEXITCODE)."
    exit 1
}

# Restore recovery policy (install resets it)
Write-Host "  Configuring service recovery..."
& sc.exe failure HomepotAgent reset= 86400 actions= restart/60000/restart/60000/restart/60000 | Out-Null

# ---------------------------------------------------------------------------
# Phase 4: Start the service
# ---------------------------------------------------------------------------

Write-Host "Phase 4/4: Starting service..."
Start-Service -Name "HomepotAgent"

$service = Get-Service -Name "HomepotAgent" -ErrorAction SilentlyContinue
if ($service -and $service.Status -eq "Running") {
    Write-Host "HOMEPOT Device Agent upgraded and running successfully."
} else {
    Write-Warning "Service re-installed but status is: $($service.Status)"
    Write-Warning "Check Event Viewer for errors."
    exit 1
}
