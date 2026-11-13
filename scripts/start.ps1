# Run NomadGrid without Docker (Windows PowerShell):  powershell -ExecutionPolicy Bypass -File scripts\start.ps1
# Creates a virtualenv, installs the backend, builds the UI if Node.js is available, starts everything.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location "$root\backend"

$py = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } elseif (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { $null }
if (-not $py) { Write-Host "Python 3.10+ is required (or use: docker compose up --build)"; exit 1 }

if (-not (Test-Path ".venv")) { & $py -m venv .venv }
$vpy = ".venv\Scripts\python.exe"
& $vpy -m pip install -q -r requirements.txt

if (-not (Test-Path "$root\frontend\dist\index.html")) {
  if (Get-Command npm -ErrorAction SilentlyContinue) {
    Write-Host "Building the web UI (first run only)..."
    Push-Location "$root\frontend"
    try { npm ci; if ($LASTEXITCODE -ne 0) { npm install }; npm run build } catch { Write-Host "UI build failed - continuing with the API only." }
    Pop-Location
  } else {
    Write-Host "Node.js not found - starting the API only. Install Node 20+ and re-run to get the web UI."
  }
}

& $vpy -m app
