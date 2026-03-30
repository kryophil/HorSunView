# install_hooks.ps1
# Richtet den Git pre-commit Hook ein (einmalig ausführen).
#
# Verwendung:
#   cd f:\dev\QGIS_HorSunView
#   .\install_hooks.ps1

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $ScriptDir

git config core.hooksPath .githooks

# Sicherstellen dass das Hook-Skript ausführbar ist (relevant für Git Bash/WSL)
$hookFile = Join-Path $ScriptDir ".githooks\pre-commit"
if (Test-Path $hookFile) {
    # Unter Windows reicht das Setzen des hooksPath; chmod ist nicht nötig
    Write-Host ""
    Write-Host "  Git Hook installiert:" -ForegroundColor Green
    Write-Host "  Bei jedem 'git commit' werden die Tests automatisch ausgefuehrt."
    Write-Host "  Fehlerhafte Tests blockieren den Commit."
} else {
    Write-Host "  FEHLER: .githooks\pre-commit nicht gefunden." -ForegroundColor Red
}

Pop-Location
Write-Host ""
