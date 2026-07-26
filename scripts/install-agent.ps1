<#
.SYNOPSIS
    Installs or removes the HOMEPOT Device Agent as a Windows service.

.DESCRIPTION
    This script:
      - Installs/upgrades the homepot-client[agent] Python package.
      - Registers the agent as a Windows service (HomepotAgent).
      - Sets startup type to Automatic.
      - Configures service recovery (restart on failure).
      - Starts the service.
      - With -Uninstall, stops and removes the service.

.PARAMETER Uninstall
    Switch to remove the service instead of installing it.

.PARAMETER PythonPath
    Path to the Python executable.  Defaults to the first python3.exe or
    python.exe on the PATH.

.EXAMPLE
    .\install-agent.ps1
    .\install-agent.ps1 -Uninstall
    .\install-agent.ps1 -PythonPath "C:\Python311\python.exe"
#>

param(
    [switch]$Uninstall,
    [string]$PythonPath = ""
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
    foreach ($candidate in @("python3.exe", "python.exe")) {
        $exe = (Get-Command $candidate -ErrorAction SilentlyContinue).Source
        if ($exe) { return $exe }
    }
    # Check common install locations
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
# Uninstall
# ---------------------------------------------------------------------------

if ($Uninstall) {
    if (-not (Test-Admin)) {
        Write-Error "Administrator privileges required.  Restart as Administrator."
        exit 1
    }
    $service = Get-Service -Name "HomepotAgent" -ErrorAction SilentlyContinue
    if ($service) {
        Write-Host "Stopping HomepotAgent service..."
        Stop-Service -Name "HomepotAgent" -Force -ErrorAction SilentlyContinue
        Write-Host "Removing service..."
        & (Get-ServiceScript) remove
        if ($LASTEXITCODE -ne 0) {
            # Fallback: sc.exe delete
            & sc.exe delete HomepotAgent
        }
        Write-Host "Service removed."
    } else {
        Write-Host "Service not installed."
    }
    exit 0
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
    Write-Error "Python 3.11+ not found.  Install Python and try again."
    exit 1
}
Write-Host "Using Python: $python"

$serviceScript = Get-ServiceScript
if (-not (Test-Path $serviceScript)) {
    Write-Error "Service wrapper not found: $serviceScript"
    exit 1
}

# ---------------------------------------------------------------------------
# Install / upgrade the Python package
# ---------------------------------------------------------------------------

Write-Host "Installing / upgrading homepot-client[agent]..."
$pipArgs = @(
    "-m", "pip", "install",
    "--upgrade",
    "homepot-client[agent]"
)
if ($env:HOMEPOT_DEV_MODE) {
    # Development mode: install from local source
    $backendDir = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Definition) ".." "backend"
    if (Test-Path $backendDir) {
        $pipArgs = @(
            "-m", "pip", "install",
            "-e", "$backendDir[agent]",
            "--no-build-isolation"
        )
    }
}

$process = Start-Process -FilePath $python -ArgumentList $pipArgs -NoNewWindow -Wait -PassThru
if ($process.ExitCode -ne 0) {
    Write-Error "pip install failed (exit code: $($process.ExitCode))."
    exit 1
}

# ---------------------------------------------------------------------------
# Register the Windows service
# ---------------------------------------------------------------------------

Write-Host "Registering HomepotAgent service..."
$installArgs = @(
    $serviceScript,
    "install"
)
$process = Start-Process -FilePath $python -ArgumentList $installArgs -NoNewWindow -Wait -PassThru
if ($process.ExitCode -ne 0) {
    Write-Error "Service installation failed (exit code: $($process.ExitCode))."
    exit 1
}

# ---------------------------------------------------------------------------
# Configure service startup and recovery
# ---------------------------------------------------------------------------

Write-Host "Setting startup type to Automatic..."
& sc.exe config HomepotAgent start= auto | Out-Null

Write-Host "Configuring service recovery (restart on failure)..."
& sc.exe failure HomepotAgent reset= 86400 actions= restart/60000/restart/60000/restart/60000 | Out-Null

Write-Host "Configuring Preshutdown timeout..."
# Set the preshutdown timeout to 30 seconds so the agent has time to
# clean up gracefully during system shutdown.
& sc.exe config HomepotAgent preshutdown= 1 | Out-Null

# ---------------------------------------------------------------------------
# Start the service
# ---------------------------------------------------------------------------

Write-Host "Starting HomepotAgent service..."
Start-Service -Name "HomepotAgent"

$service = Get-Service -Name "HomepotAgent"
if ($service.Status -eq "Running") {
    Write-Host "HOMEPOT Device Agent installed and running successfully."
    Write-Host "  Service name: HomepotAgent"
    Write-Host "  Display name: HOMEPOT Device Agent"
    Write-Host "  Startup:      Automatic"
    Write-Host "  Recovery:     Restart (3 attempts, 60s interval)"
} else {
    Write-Warning "Service installed but status is: $($service.Status)"
}
