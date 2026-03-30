# make_zip.ps1
# Erstellt ein QGIS-kompatibles Plugin-ZIP für HorSunView.
#
# Verwendung (PowerShell):
#   cd f:\dev\QGIS_HorSunView
#   .\make_zip.ps1
#
# Das erzeugte ZIP kann in QGIS direkt über
#   Erweiterungen → Aus ZIP installieren
# eingespielt werden.

$PluginName = "HorSunView"
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path

# Version aus metadata.txt lesen
$Version = (Get-Content "$ScriptDir\metadata.txt" |
            Where-Object { $_ -match "^version=" }) -replace "version=", "" -replace "\s", ""
$ZipName = "${PluginName}_v${Version}.zip"
$ZipPath = Join-Path $ScriptDir $ZipName

# Ordner/Dateien, die NICHT ins ZIP gehören
$ExcludeDirs  = @('.git', '__pycache__', 'tests')
$ExcludeFiles = @('make_zip.sh', 'make_zip.ps1', '.gitignore', '*.zip')

# Temporäres Verzeichnis mit korrekter QGIS-Struktur:
#   <temp>\HorSunView\   ← QGIS erwartet genau diesen Unterordner
$TempBase   = Join-Path $env:TEMP "qgis_plugin_build_$(Get-Random)"
$TempPlugin = Join-Path $TempBase $PluginName
New-Item -ItemType Directory -Path $TempPlugin | Out-Null

# Dateien kopieren
Get-ChildItem -Path $ScriptDir | ForEach-Object {
    $item = $_

    # Ordner ausschliessen
    if ($item.PSIsContainer) {
        if ($ExcludeDirs -notcontains $item.Name) {
            Copy-Item -Path $item.FullName -Destination $TempPlugin -Recurse
        }
        return
    }

    # Einzeldateien ausschliessen
    $skip = $false
    foreach ($pattern in $ExcludeFiles) {
        if ($item.Name -like $pattern) { $skip = $true; break }
    }
    if (-not $skip) {
        Copy-Item -Path $item.FullName -Destination $TempPlugin
    }
}

# __pycache__ aus Unterordnern entfernen
Get-ChildItem -Path $TempBase -Filter '__pycache__' -Recurse -Directory |
    Remove-Item -Recurse -Force

# Altes ZIP löschen, neues erstellen
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path "$TempBase\*" -DestinationPath $ZipPath

# Temporären Ordner aufräumen
Remove-Item -Path $TempBase -Recurse -Force

# Erfolgsmeldung
$Size = [math]::Round((Get-Item $ZipPath).Length / 1KB, 0)
Write-Host ""
Write-Host "  ZIP erstellt: $ZipPath" -ForegroundColor Green
Write-Host "  Version:      $Version"
Write-Host "  Groesse:      ${Size} KB"
Write-Host ""
Write-Host "In QGIS installieren:" -ForegroundColor Cyan
Write-Host "  Erweiterungen -> Aus ZIP installieren -> Datei waehlen -> Erweiterung installieren"
Write-Host ""
