from datetime import datetime, timedelta
from qgis.core import QgsMessageLog, Qgis
# -*- coding: utf-8 -*-
from qgis.core import QgsTask, QgsMessageLog, Qgis, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject
import numpy as np
import pandas as pd
import os
from osgeo import gdal
from .plotting import Plotter
from .spa_nrel import spa_calculate

class HorizonAnalysisTask(QgsTask):
    def get_height(self, x, y):
        from qgis.core import QgsPointXY, QgsRaster
        prov = self.dem_layer.dataProvider()
        res = prov.identify(QgsPointXY(x, y), QgsRaster.IdentifyFormatValue)
        return res.results().get(1) if res.isValid() else None

    def __init__(self, dem_layer, x, y, year, place, out_dir, iface):
        description = f"Horizontprofil und Sonnenbahnen berechnen für Punkt ({x},{y})"
        super().__init__(description, QgsTask.CanCancel)
        self.dem_layer = dem_layer
        self.coords = (x, y)
        self.year = year
        self.place = place
        self.prefix = place.replace(" ", "_")
        self.out_dir = out_dir
        self.iface = iface
        self._dem_array = None
        self._gt = None

    def run(self):
        try:
            # prepare output directory
            os.makedirs(self.out_dir, exist_ok=True)

            # Load DEM using GDAL into numpy array
            ds = gdal.Open(self.dem_layer.dataProvider().dataSourceUri())
            band = ds.GetRasterBand(1)
            dem_array = band.ReadAsArray()
            self._dem_array = dem_array
            self._rows, self._cols = dem_array.shape
            self._gt = ds.GetGeoTransform()
            ds = None  # close dataset

            # Compute z0
            self.setProgress(20)
            z0 = self.get_height(self.coords[0], self.coords[1])

            # Compute horizon profile
            self.setProgress(50)
            horizon_df = self.compute_horizon()

            # Compute SVF
            self.setProgress(70)
            svf = self.compute_svf(horizon_df)

            # Compute sun paths
            self.setProgress(90)
            sun_paths = self.compute_sun_paths()

            # Plot and save
            # instanziere Plotter und rufe Instanzmethode auf
            plotter = Plotter(self.prefix, self.out_dir)
            plotter.plot_and_save(horizon_df, svf, sun_paths, self.coords, self.year, self.place,self.iface)

            self.setProgress(100)
            return True
        except Exception as e:
            QgsMessageLog.logMessage(f"Fehler in HorizonAnalysisTask: {e}", "HorSunView", Qgis.Critical)
            return False

    def finished(self, result):
        if result:
            msg = f"Horizontprofil und Sonnenbahnen berechnet. Dateien: {self.out_dir}"
            self.iface.messageBar().pushMessage("HorSunView", msg, level=Qgis.Success)
        else:
            self.iface.messageBar().pushMessage("HorSunView", "Fehler bei der Berechnung.", level=Qgis.Critical)
    def compute_horizon(self):
        
        
        # DEM coverage check - warn only (keep max_dist=10000)
        max_dist = 10000
        extent = self.dem_layer.extent()
        x0, y0 = self.coords
        # compute minimal distance to boundary
        dmin = min(x0 - extent.xMinimum(), extent.xMaximum() - x0,
                   y0 - extent.yMinimum(), extent.yMaximum() - y0)
        if dmin < max_dist:
            QgsMessageLog.logMessage(
                f"Warnung: DEM deckt nur {dmin:.0f} m um ({x0:.1f}, {y0:.1f}) ab, aber gerenderte Horizon-Berechnung nutzt weiterhin 10000 m.",
                "HorSunView", Qgis.Warning
            )
        # get base elevation
        z0 = self.get_height(x0, y0)
        if z0 is None:
            msg = f"Höhe am Standort ({x0:.1f}, {y0:.1f}) konnte nicht ermittelt werden."
            QgsMessageLog.logMessage(msg, "HorSunView", Qgis.Critical)
            raise Exception(msg)
        observer_elev = z0 + 2.0



        # Azimuth angles
        azs = np.arange(0, 361)  # include 360 for closure
        angles = []
        step = max(2, int(round(min(self.dem_layer.rasterUnitsPerPixelX(), self.dem_layer.rasterUnitsPerPixelY()))))
        for az in azs:
            max_ang = -90
            for d in np.arange(step, max_dist, step):
                x1 = x0 + np.sin(np.radians(az)) * d
                y1 = y0 + np.cos(np.radians(az)) * d
                h = self.get_height(x1, y1)
                if h is not None:
                    ang = np.degrees(np.arctan2(h - observer_elev, d))
                    max_ang = max(max_ang, ang)
            angles.append(max_ang)
        df = pd.DataFrame({'azimut': azs, 'horizontwinkel': angles})
        df['hoehe_standort'] = z0

        # ensure closure
        # already 360 added in azs with same angle logic

        df.to_csv(os.path.join(self.out_dir, 'horizontprofil.csv'), index=False, float_format='%.3f')
        return df

    def compute_svf(self, horizon_df):
        beta = np.deg2rad(horizon_df['horizontwinkel'][:-1])
        dtheta = 2 * np.pi / len(beta)
        return (1/(2*np.pi)) * np.sum(np.cos(beta)**2 * dtheta)

    def compute_sun_paths(self):
        from datetime import datetime, timedelta
        import numpy as np, pandas as pd, os
        x0, y0 = self.coords
        crs_src = QgsCoordinateReferenceSystem('EPSG:2056')
        crs_dest = QgsCoordinateReferenceSystem('EPSG:4326')
        transformer = QgsCoordinateTransform(crs_src, crs_dest, QgsProject.instance())
        pt = transformer.transform(x0, y0)
        lon, lat = pt.x(), pt.y()
        # Custom mapping: specific 21sts with labels
        months = [
            (12, "21. Dez."),
            (1,  "21. Jan./Nov."),
            (2,  "21. Feb./Okt."),
            (3,  "21. Mar./Sep."),
            (4,  "21. Apr./Aug."),
            (5,  "21. Mai/Jul."),
            (6,  "21. Jun.")
        ]
        paths = {}
        for m, lbl in months:
            start = datetime(self.year, m, 21, 0, 0)
            end   = datetime(self.year, m, 21, 23, 59)
            total_minutes = int((end - start).total_seconds() // 60)
            times = [start + timedelta(minutes=i) for i in range(0, total_minutes+1, 5)]
            rows = []
            for t in times:
                az, el = spa_calculate(t, lat, lon, self.get_height(x0, y0))
                rows.append({'azimut': az, 'höhe': el})
            df_all = pd.DataFrame(rows)
            # sunrise/sunset interpolation at 0°
            els = df_all['höhe'].values; azs = df_all['azimut'].values
            idx = np.where(els >= 0)[0]
            sunrise_az = sunset_az = None
            if idx.size:
                i0 = idx[0]
                if i0>0:
                    f = -els[i0-1]/(els[i0]-els[i0-1])
                    sunrise_az = azs[i0-1] + f*(azs[i0]-azs[i0-1])
                else:
                    sunrise_az = azs[0]
                i1 = idx[-1]
                if i1 < len(els)-1:
                    f2 = -els[i1]/(els[i1+1]-els[i1])
                    sunset_az = azs[i1] + f2*(azs[i1+1]-azs[i1])
                else:
                    sunset_az = azs[-1]
            extra = []
            if sunrise_az is not None:
                extra.append({'azimut': sunrise_az, 'höhe': 0.0})
            if sunset_az is not None:
                extra.append({'azimut': sunset_az, 'höhe': 0.0})
            df_out = pd.concat([pd.DataFrame(extra), df_all], ignore_index=True)
            df_out = df_out.sort_values('azimut').reset_index(drop=True)
            filename = f"{self.prefix}_sonnenbahn_{m:02d}.csv"
            df_out.to_csv(os.path.join(self.out_dir, filename), index=False, float_format='%.3f')
            paths[lbl] = df_out
        return paths




    def get_height(self, x, y):
        # Convert world coordinates to array indices using geotransform
        gt = self._gt
        # gt: (originX, pixelWidth, 0, originY, 0, pixelHeight)
        px = int((x - gt[0]) / gt[1])
        py = int((y - gt[3]) / gt[5])
        if 0 <= px < self._cols and 0 <= py < self._rows:
            return float(self._dem_array[py, px])
        else:
            return None
