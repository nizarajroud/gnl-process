<#
.SYNOPSIS
    Launch GNL Process in a dedicated, isolated Chrome window (app mode).

.DESCRIPTION
    Opens Chrome in "app mode" (no tab bar, no address bar) pointing at the local
    GNL Process server, using a DEDICATED profile in %LOCALAPPDATA%\gnl-process-chrome.
    (Inspired by the kiro-web launcher.)

    The GNL server runs as a systemd service in WSL on port 8001 (prod). No manual
    start needed; check with 'gnl-prod status' / 'systemctl status gnl-process'.

.PARAMETER Port
    Local port GNL listens on. Default: 8001 (prod).

.EXAMPLE
    .\launch-chrome.ps1
#>
param(
    [int]$Port = 8001
)

$ErrorActionPreference = 'Stop'

# --- Locate chrome.exe ---
$candidates = @(
    "$Env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${Env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$Env:LocalAppData\Google\Chrome\Application\chrome.exe"
)
$chrome = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $chrome) {
    $cmd = Get-Command chrome.exe -ErrorAction SilentlyContinue
    if ($cmd) { $chrome = $cmd.Source }
}
if (-not $chrome) {
    Write-Error "chrome.exe not found. Install Google Chrome or add it to PATH."
    exit 1
}

# --- Dedicated, isolated profile ---
$profileDir = Join-Path $Env:LocalAppData 'gnl-process-chrome'
if (-not (Test-Path $profileDir)) {
    New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
}

$url = "http://127.0.0.1:$Port"

# --- Warn if the server is not up yet (non-fatal) ---
try {
    $null = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
} catch {
    Write-Warning "GNL Process ne répond pas encore sur $url. Vérifier le service (systemctl status gnl-process)."
}

Write-Host "Ouverture de GNL Process dans Chrome (profil dédié, sans extensions)..." -ForegroundColor Cyan
Write-Host "  URL    : $url"
Write-Host "  Profile: $profileDir"

& $chrome `
    "--app=$url" `
    "--user-data-dir=$profileDir" `
    "--start-maximized" `
    "--no-first-run" `
    "--no-default-browser-check" `
    "--new-window"
