<#
.SYNOPSIS
    Crée un raccourci Bureau qui ouvre GNL Process directement dans une fenêtre
    Chrome dédiée (mode app), avec l'icône GNL. (Inspiré de kiro-web.)

.DESCRIPTION
    À exécuter UNE FOIS depuis Windows. Le raccourci cible chrome.exe DIRECTEMENT
    en mode app + profil isolé (%LOCALAPPDATA%\gnl-process-chrome) : aucune
    extension, mémoire isolée, fenêtre propre. Clic = ouverture instantanée, sans
    console PowerShell.

    Le serveur GNL tourne en service systemd (WSL) sur le port 8001 (prod).

.PARAMETER Port
    Port local de GNL. Défaut : 8001 (prod).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\install-shortcut.ps1
#>
param(
    [int]$Port = 8001
)

$ErrorActionPreference = 'Stop'

# --- Localiser chrome.exe ---
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
    Write-Error "chrome.exe introuvable. Installer Google Chrome ou l'ajouter au PATH."
    exit 1
}

# --- Icône du repo -> copier vers un chemin Windows stable (le repo peut être sous \\wsl$) ---
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$iconSrc   = Join-Path (Split-Path -Parent $scriptDir) 'web\img\gnl-icon.ico'
$appDir    = Join-Path $Env:LocalAppData 'gnl-process'
if (-not (Test-Path $appDir)) { New-Item -ItemType Directory -Path $appDir -Force | Out-Null }
$iconDst = Join-Path $appDir 'gnl-icon.ico'
if (Test-Path $iconSrc) { Copy-Item $iconSrc $iconDst -Force } else { $iconDst = $chrome }

# --- Profil Chrome dédié (isolé, sans extensions) ---
$profileDir = Join-Path $Env:LocalAppData 'gnl-process-chrome'
if (-not (Test-Path $profileDir)) { New-Item -ItemType Directory -Path $profileDir -Force | Out-Null }

$url = "http://127.0.0.1:$Port"

# --- Créer le raccourci pointant DIRECTEMENT sur chrome.exe (pas de PowerShell) ---
$desktop = [Environment]::GetFolderPath('Desktop')
$lnkPath = Join-Path $desktop 'GNL Process.lnk'

$chromeArgs = "--app=$url --user-data-dir=`"$profileDir`" --start-maximized --no-first-run --no-default-browser-check"

$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut($lnkPath)
$sc.TargetPath       = $chrome
$sc.Arguments        = $chromeArgs
$sc.WorkingDirectory = Split-Path -Parent $chrome
$sc.Description      = 'Ouvrir GNL Process (fenêtre Chrome dédiée)'
$sc.IconLocation     = $iconDst
$sc.Save()

Write-Host "OK - Raccourci créé : $lnkPath" -ForegroundColor Green
Write-Host "  Cible : $chrome $chromeArgs"
Write-Host "  Icône : $iconDst"
Write-Host ""
Write-Host "Rappel : pointe sur la PROD (service systemd sur 8001). Le service tourne en permanence." -ForegroundColor Yellow
