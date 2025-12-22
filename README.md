# HorSunView

**HorSunView** ist ein QGIS-Plugin zur Berechnung von

- **Horizontprofil / Horizontlinie** (Horizon line)
- **Sky View Factor (SVF)**
- **Sonnenbahnen** (Sonnenstanddiagramm)

auf Basis eines **Digitalen Höhenmodells (DEM)** im Schweizer Koordinatensystem **LV95 (EPSG:2056)**. :contentReference[oaicite:1]{index=1}

Das Plugin erzeugt **CSV-Dateien** und eine **PNG-Grafik** (Sonnenstanddiagramm inkl. Horizont und SVF). :contentReference[oaicite:2]{index=2}

## Features (Ist-Stand)

- Eingabe: DEM-Layer (Raster), Standortkoordinaten (E/N in LV95), Ortsname (Titel/Dateiprefix). :contentReference[oaicite:3]{index=3}
- Horizontprofil: 0–360° (1°-Schritt), maximale Sichtdistanz aktuell **10 km**, Beobachterhöhe **+2 m**. :contentReference[oaicite:4]{index=4}
- SVF-Berechnung aus dem Horizontprofil (diskrete Azimut-Integration). :contentReference[oaicite:5]{index=5}
- Sonnenbahnen am **21. Tag** ausgewählter Monate (symmetrische Monate als gemeinsame Kurve/Labelling). :contentReference[oaicite:6]{index=6}
- Sunrise/Sunset: Interpolation bei Elevation = 0°. :contentReference[oaicite:7]{index=7}
- Export: `horizontprofil.csv`, mehrere `*_sonnenbahn_MM.csv`, sowie `*_horizont_sonnenbahn_gesamt.png`. 

## Voraussetzungen

- **QGIS ≥ 3.10** :contentReference[oaicite:9]{index=9}
- DEM-Raster im Projekt (idealerweise in **LV95 / EPSG:2056**)
- Schreibrechte im Ausgabeverzeichnis (aktuell: Ordner der QGIS-Projektdatei)

## Installation (Entwicklung / lokal)

1. Repository klonen oder als ZIP herunterladen.
2. Plugin-Ordner in das lokale QGIS-Plugin-Verzeichnis kopieren, z. B. unter Windows:
   - `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\HorSunView`
3. QGIS neu starten und Plugin in **Erweiterungen → Erweiterungen verwalten und installieren…** aktivieren.

> Hinweis: Für Releases ist später ein Plugin-ZIP sinnvoll (QGIS Plugin Builder/Release-Workflow).

## Nutzung

1. In QGIS ein DEM-Raster laden.
2. Plugin über Toolbar oder Menü **HorSunView** starten.
3. Eingaben:
   - Höhenmodell (Rasterlayer)
   - Ostwert / Nordwert (LV95)
   - Ortsname (für Titel/Dateinamen)
4. Plugin startet eine Hintergrundberechnung und erzeugt die Output-Dateien.

## Output

Im Ordner der QGIS-Projektdatei werden u. a. erzeugt:

- `horizontprofil.csv`  
  Spalten: `azimut`, `horizontwinkel`, `hoehe_standort` :contentReference[oaicite:10]{index=10}
- `{PREFIX}_sonnenbahn_{MM}.csv` (mehrere Monate)  
  Spalten: `azimut`, `höhe` :contentReference[oaicite:11]{index=11}
- `{PREFIX}_horizont_sonnenbahn_gesamt.png` :contentReference[oaicite:12]{index=12}

## Referenzen

- Marks & Dozier (1979): SVF-Konzept; zitiert in Whiteman et al. (2004) :contentReference[oaicite:13]{index=13}
- Reda & Andreas (2008): Solar Position Algorithm (SPA) :contentReference[oaicite:14]{index=14}

## Bekannte Punkte / ToDo

Diese Liste ist als Arbeitsliste gedacht (Ist-Analyse, Stand heute):

- Stundenlinien-Label im Plot: Variable `solar_time` ist derzeit nicht gesetzt → Plot-Fehler möglich. :contentReference[oaicite:15]{index=15}
- Dezemberkurve wird im Plot mehrfach gezeichnet (Logikfehler). :contentReference[oaicite:16]{index=16}
- Sonnenstandsberechnung basiert auf einer Eigenimplementierung („spa_nrel.py“) und muss gegen eine Referenz (NOAA/pvlib/SPA-Portierung) validiert werden. 
- In `analysis.py` existieren zwei `get_height()`-Definitionen (eine überschreibt die andere) → Cleanup. 

## Lizenz

Noch nicht festgelegt. (Optional: MIT/Apache-2.0, falls das Repo public bleiben soll.)
