# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from qgis.core import (
    QgsTask, QgsMessageLog, Qgis,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject
)
import numpy as np
import pandas as pd
import os
from osgeo import gdal
from .plotting import Plotter
from .spa_nrel import spa_calculate


class HorizonAnalysisTask(QgsTask):
    """
    Hintergrund-Task für Horizontprofil, SVF und Sonnenbahnen.
    Alle schweren Berechnungen laufen im Worker-Thread (run()).
    GUI-Aufrufe NUR in finished() – dort ist der Main-Thread garantiert.
    """

    def __init__(self, dem_layer, x, y, year, place, out_dir, iface, az_step=0.5):
        description = f"Horizontprofil und Sonnenbahnen für ({x:.1f}, {y:.1f})"
        super().__init__(description, QgsTask.CanCancel)
        self.dem_layer = dem_layer
        self.coords = (x, y)
        self.year = year
        self.place = place
        self.prefix = place.replace(" ", "_")
        self.out_dir = out_dir
        self.iface = iface          # nur in finished() verwenden!
        self.az_step = float(az_step)
        self._dem_array = None
        self._gt = None
        self._rows = self._cols = 0

    # ------------------------------------------------------------------
    # Hilfsmethode: Höhe aus vorgeladenem GDAL-Array (thread-safe)
    # ------------------------------------------------------------------
    def get_height(self, x, y):
        """Gibt die Geländehöhe an (x, y) zurück, oder None wenn ausserhalb."""
        gt = self._gt
        px = int((x - gt[0]) / gt[1])
        py = int((y - gt[3]) / gt[5])
        if 0 <= px < self._cols and 0 <= py < self._rows:
            return float(self._dem_array[py, px])
        return None

    # ------------------------------------------------------------------
    # Hauptablauf (Worker-Thread)
    # ------------------------------------------------------------------
    def run(self):
        try:
            os.makedirs(self.out_dir, exist_ok=True)

            # DEM einlesen
            ds = gdal.Open(self.dem_layer.dataProvider().dataSourceUri())
            if ds is None:
                raise RuntimeError("GDAL konnte das DEM nicht öffnen.")
            band = ds.GetRasterBand(1)
            self._dem_array = band.ReadAsArray()
            self._rows, self._cols = self._dem_array.shape
            self._gt = ds.GetGeoTransform()
            ds = None  # Dataset schliessen

            self.setProgress(10)
            if self.isCanceled():
                return False

            # Horizontprofil
            horizon_df = self.compute_horizon()
            if self.isCanceled():
                return False

            # SVF
            svf = self.compute_svf(horizon_df)
            self.setProgress(70)

            # Sonnenbahnen
            sun_paths = self.compute_sun_paths()
            self.setProgress(90)

            # Plot & Speichern (kein iface hier!)
            plotter = Plotter(self.prefix, self.out_dir)
            plotter.plot_and_save(
                horizon_df, svf, sun_paths,
                self.coords, self.year, self.place
            )

            self.setProgress(100)
            return True

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Fehler in HorizonAnalysisTask: {e}", "HorSunView", Qgis.Critical
            )
            return False

    def finished(self, result):
        """Wird im Main-Thread aufgerufen – GUI-Zugriffe sind hier sicher."""
        if result:
            msg = f"Fertig. Dateien gespeichert in: {self.out_dir}"
            self.iface.messageBar().pushMessage("HorSunView", msg, level=Qgis.Success)
        else:
            self.iface.messageBar().pushMessage(
                "HorSunView",
                "Fehler bei der Berechnung. Details im QGIS-Nachrichtenprotokoll.",
                level=Qgis.Critical
            )

    # ------------------------------------------------------------------
    # Horizontprofil
    # ------------------------------------------------------------------
    def compute_horizon(self):
        """
        Berechnet das Horizontprofil für den Standort.

        Verbesserungen gegenüber der ursprünglichen Version:
          - NumPy-Vektorisierung des inneren Distanz-Loops (~100× schneller)
          - Erdkrümmungskorrektur: Terrain wirkt auf Distanz d um d²/(2R) niedriger
          - Azimut-Auflösung konfigurierbar (self.az_step, Standard 0.5°)
          - Abbruch via isCanceled() zwischen Azimut-Schritten möglich
        """
        MAX_DIST = 10_000.0   # m
        R_EARTH  = 6_371_000.0
        x0, y0 = self.coords

        # Ausdehnung prüfen (Warnung, kein Abbruch)
        extent = self.dem_layer.extent()
        dmin = min(
            x0 - extent.xMinimum(), extent.xMaximum() - x0,
            y0 - extent.yMinimum(), extent.yMaximum() - y0
        )
        if dmin < MAX_DIST:
            QgsMessageLog.logMessage(
                f"Warnung: DEM deckt nur {dmin:.0f} m um den Standort ab "
                f"(benötigt: {MAX_DIST:.0f} m).",
                "HorSunView", Qgis.Warning
            )

        z0 = self.get_height(x0, y0)
        if z0 is None:
            raise RuntimeError(
                f"Keine Höhe am Standort ({x0:.1f}, {y0:.1f}) – "
                "Punkt liegt ausserhalb des DEM."
            )
        observer_elev = z0 + 2.0  # Augenhöhe

        # Schrittweite = Pixelgrösse (mindestens 2 m)
        pixel_size = max(
            2,
            int(round(min(
                self.dem_layer.rasterUnitsPerPixelX(),
                self.dem_layer.rasterUnitsPerPixelY()
            )))
        )

        gt = self._gt

        # Alle Distanzen einmalig berechnen (vektorisiert)
        distances = np.arange(pixel_size, MAX_DIST + pixel_size, pixel_size,
                              dtype=float)
        # Erdkrümmungskorrektur: Terrain auf Distanz d erscheint um d²/(2R) niedriger
        curvature = distances ** 2 / (2.0 * R_EARTH)

        # Azimut-Raster inkl. Schlusspunkt 360° = 0° (für Closure im Plot/SVF)
        n_az = round(360.0 / self.az_step)
        azs = np.linspace(0.0, 360.0, n_az + 1)
        angles = np.full(len(azs), -90.0)

        for i, az in enumerate(azs):
            # Abbruch-Check (QGIS Task-Mechanismus)
            if self.isCanceled():
                raise RuntimeError("Berechnung vom Benutzer abgebrochen.")

            sin_az = np.sin(np.radians(az))
            cos_az = np.cos(np.radians(az))

            # Alle Stichprobenpunkte entlang des Strahls auf einmal
            xs = x0 + sin_az * distances
            ys = y0 + cos_az * distances

            pxs = ((xs - gt[0]) / gt[1]).astype(int)
            pys = ((ys - gt[3]) / gt[5]).astype(int)

            valid = (
                (pxs >= 0) & (pxs < self._cols) &
                (pys >= 0) & (pys < self._rows)
            )

            if valid.any():
                h = self._dem_array[pys[valid], pxs[valid]].astype(float)
                # Erdkrümmung abziehen: entfernte Punkte wirken niedriger
                h_corr = h - curvature[valid]
                el = np.degrees(
                    np.arctan2(h_corr - observer_elev, distances[valid])
                )
                angles[i] = float(el.max())

            # Fortschritt: 10 % (nach DEM-Laden) … 60 % (Horizont fertig)
            if i % max(1, n_az // 20) == 0:
                self.setProgress(10 + int(50 * i / n_az))

        df = pd.DataFrame({'azimut': azs, 'horizontwinkel': angles})
        df['hoehe_standort'] = z0
        df.to_csv(
            os.path.join(self.out_dir, 'horizontprofil.csv'),
            index=False, float_format='%.3f'
        )
        return df

    # ------------------------------------------------------------------
    # Sky View Factor (Marks & Dozier 1979, zitiert in Whiteman 2004)
    # ------------------------------------------------------------------
    def compute_svf(self, horizon_df):
        # 360°-Wert (= 0°) weglassen, um Doppelzählung zu vermeiden
        beta = np.deg2rad(horizon_df['horizontwinkel'].values[:-1])
        dtheta = 2 * np.pi / len(beta)
        return float((1 / (2 * np.pi)) * np.sum(np.cos(beta) ** 2 * dtheta))

    # ------------------------------------------------------------------
    # Sonnenbahnen (SPA, Reda & Andreas 2008)
    # ------------------------------------------------------------------
    def compute_sun_paths(self):
        x0, y0 = self.coords

        # Einmalige Koordinatentransformation LV95 → WGS84
        crs_src = QgsCoordinateReferenceSystem('EPSG:2056')
        crs_dst = QgsCoordinateReferenceSystem('EPSG:4326')
        transformer = QgsCoordinateTransform(crs_src, crs_dst, QgsProject.instance())
        pt = transformer.transform(x0, y0)
        lon, lat = pt.x(), pt.y()

        # Standorthöhe einmalig holen (nicht im Loop!)
        z0 = self.get_height(x0, y0) or 0.0

        # Symmetrische Monate als gemeinsame Kurve
        months = [
            (12, "21. Dez"),
            (1,  "21. Jan/Nov"),
            (2,  "21. Feb/Okt"),
            (3,  "21. Mär/Sep"),
            (4,  "21. Apr/Aug"),
            (5,  "21. Mai/Jul"),
            (6,  "21. Jun"),
        ]

        paths = {}
        for m, lbl in months:
            start = datetime(self.year, m, 21, 0, 0)
            times = [start + timedelta(minutes=i) for i in range(0, 24 * 60 + 1, 5)]
            rows = []
            for t in times:
                az, el = spa_calculate(t, lat, lon, z0)
                rows.append({'azimut': az, 'höhe': el})

            df_all = pd.DataFrame(rows)

            # Sonnenauf-/-untergang interpolieren (Elevation = 0°)
            els = df_all['höhe'].values
            azs_arr = df_all['azimut'].values
            idx_above = np.where(els >= 0)[0]

            extra = []
            if idx_above.size:
                i0 = idx_above[0]
                if i0 > 0:
                    f = -els[i0 - 1] / (els[i0] - els[i0 - 1])
                    extra.append({
                        'azimut': azs_arr[i0-1] + f * (azs_arr[i0] - azs_arr[i0-1]),
                        'höhe': 0.0
                    })
                else:
                    extra.append({'azimut': azs_arr[0], 'höhe': 0.0})

                i1 = idx_above[-1]
                if i1 < len(els) - 1:
                    f2 = -els[i1] / (els[i1+1] - els[i1])
                    extra.append({
                        'azimut': azs_arr[i1] + f2 * (azs_arr[i1+1] - azs_arr[i1]),
                        'höhe': 0.0
                    })
                else:
                    extra.append({'azimut': azs_arr[-1], 'höhe': 0.0})

            df_out = pd.concat(
                [pd.DataFrame(extra), df_all], ignore_index=True
            ).sort_values('azimut').reset_index(drop=True)

            fname = f"{self.prefix}_sonnenbahn_{m:02d}.csv"
            df_out.to_csv(
                os.path.join(self.out_dir, fname),
                index=False, float_format='%.3f'
            )
            paths[lbl] = df_out

        return paths
