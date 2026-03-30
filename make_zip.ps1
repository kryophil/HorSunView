# make_zip.ps1
# Erstellt ein QGIS-kompatibles Plugin-ZIP und inkrementiert die Versionsnummer.
#
# Verwendung:
#   .\make_zip.ps1           → PATCH erhöhen  (z. B. 2.0.0 → 2.0.1)
#   .\make_zip.ps1 -Minor    → MINOR erhöhen  (z. B. 2.0.1 → 2.1.0)
#   .\make_zip.ps1 -Major    → MAJOR erhöhen  (z. B. 2.1.0 → 3.0.0)
#   .\make_zip.ps1 -NoBump   → Version NICHT ändern (nur ZIP erstellen)

param(
    [switch]$Major,
    [switch]$Minor,
    [switch]$NoBump
)

$PluginName   = "HorSunView"
$ScriptDir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$MetadataPath = Join-Path $ScriptDir "metadata.txt"

# ── 1. Version lesen ─────────────────────────────────────────────────────────
$Metadata = Get-Content $MetadataPath -Encoding UTF8
$VersionLine = $Metadata | Where-Object { $_ -match "^version=" }
if (-not $VersionLine) {
    Write-Host "FEHLER: Keine 'version='-Zeile in metadata.txt gefunden." -ForegroundColor Red
    exit 1
}
$CurrentVersion = ($VersionLine -replace "^version=", "").Trim()
$Parts = $CurrentVersion -split '\.'
if ($Parts.Count -ne 3) {
    Write-Host "FEHLER: Version muss MAJOR.MINOR.PATCH sein (aktuell: $CurrentVersion)" -ForegroundColor Red
    exit 1
}
[int]$Maj = $Parts[0]
[int]$Min = $Parts[1]
[int]$Pat = $Parts[2]

# ── 2. Version inkrementieren ─────────────────────────────────────────────────
if (-not $NoBump) {
    if ($Major)      { $Maj++; $Min = 0; $Pat = 0 }
    elseif ($Minor)  { $Min++; $Pat = 0 }
    else             { $Pat++ }   # Standard: Patch

    $NewVersion = "$Maj.$Min.$Pat"
    $NewMetadata = $Metadata -replace "^version=.*", "version=$NewVersion"
    $NewMetadata | Set-Content $MetadataPath -Encoding UTF8

    Write-Host ""
    Write-Host "  Version: $CurrentVersion  ->  $NewVersion" -ForegroundColor Yellow
} else {
    $NewVersion = $CurrentVersion
    Write-Host ""
    Write-Host "  Version: $NewVersion (unveraendert)" -ForegroundColor Gray
}

$ZipName = "${PluginName}_v${NewVersion}.zip"
$ZipPath = Join-Path $ScriptDir $ZipName

# ── 3. ZIP erstellen ──────────────────────────────────────────────────────────
$ExcludeDirs  = @('.git', '__pycache__', 'tests')
$ExcludeFiles = @('make_zip.sh', 'make_zip.ps1', '.gitignore', '*.zip')

$TempBase   = Join-Path $env:TEMP "qgis_plugin_build_$(Get-Random)"
$TempPlugin = Join-Path $TempBase $PluginName
New-Item -ItemType Directory -Path $TempPlugin | Out-Null

Get-ChildItem -Path $ScriptDir | ForEach-Object {
    $item = $_
    if ($item.PSIsContainer) {
        if ($ExcludeDirs -notcontains $item.Name) {
            Copy-Item -Path $item.FullName -Destination $TempPlugin -Recurse
        }
        return
    }
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

if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path "$TempBase\*" -DestinationPath $ZipPath
Remove-Item -Path $TempBase -Recurse -Force

$Size = [math]::Round((Get-Item $ZipPath).Length / 1KB, 0)
Write-Host "  ZIP:     $ZipPath" -ForegroundColor Green
Write-Host "  Groesse: ${Size} KB"

# ── 4. Git commit & push (nur wenn Version geändert wurde) ───────────────────
if (-not $NoBump) {
    Write-Host ""
    Write-Host "  Git: Versionsnummer committen und pushen ..." -ForegroundColor Cyan

    Push-Location $ScriptDir
    try {
        git add metadata.txt | Out-Null
        git commit -m "chore: version $CurrentVersion -> $NewVersion" | Out-Null
        git push | Out-Null
        Write-Host "  Git: OK (Version $NewVersion auf GitHub)" -ForegroundColor Green
    } catch {
        Write-Host "  Git: Fehler beim Commit/Push – bitte manuell ausfuehren." -ForegroundColor Red
        Write-Host "       git add metadata.txt"
        Write-Host "       git commit -m `"chore: version $NewVersion`""
        Write-Host "       git push"
    }
    Pop-Location
}

# ── 5. Abschluss ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "In QGIS installieren:" -ForegroundColor Cyan
Write-Host "  Erweiterungen -> Aus ZIP installieren -> Datei waehlen -> Erweiterung installieren"
Write-Host ""
