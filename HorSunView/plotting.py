# -*- coding: utf-8 -*-
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os
from datetime import datetime, timezone
from .spa_nrel import spa_calculate
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject, QgsMessageLog, Qgis

class Plotter:
    def __init__(self, prefix, out_dir):
        self.prefix = prefix
        self.out_dir = out_dir

    def plot_and_save(self, horizon_df, svf, sun_paths, coords, year, place, iface):
        try:
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.set_xlim(0, 360); ax.set_ylim(0, 90)
            ax.grid(True, which='major', axis='x', linestyle='--', linewidth=0.5)
            ax.grid(True, which='major', axis='y', linestyle='--', linewidth=0.5)

            # Fill horizon
            ax.fill_between(horizon_df['azimut'], horizon_df['horizontwinkel'], color='grey', alpha=0.3)
            ax.plot(horizon_df['azimut'], horizon_df['horizontwinkel'], color='black', linewidth=2)

            # Plot sun paths
            # Plot all except December first (damit Dez nicht untergezeichnet wird)
            for lbl, df in sun_paths.items():
                if lbl != "21. Dez.":
                    ax.plot(df['azimut'], df['höhe'], linestyle='-', color='black', linewidth=1)
                    idx_max = df['höhe'].idxmax()
                    ax.text(df.at[idx_max, 'azimut'], df.at[idx_max, 'höhe'] + 2, lbl, fontsize=8, ha='center', va='bottom', clip_on=False)

                # … und ganz zum Schluss den Dezember-Pfad dicker auftragen …
                if "21. Dez." in sun_paths:
                    df = sun_paths["21. Dez."]
                    ax.plot(df['azimut'], df['höhe'], linestyle='-', color='black', linewidth=2)
                    idx_max = df['höhe'].idxmax()
                    ax.text(df.at[idx_max, 'azimut'], df.at[idx_max, 'höhe'] + 2, "21. Dez.", fontsize=8, ha='center', va='bottom', clip_on=False)

            # Annotation
            title = f"Sonnenstanddiagramm {place}" if place else "Sonnenstanddiagramm"
            ax.set_title(title)
            ax.set_xlabel('Azimut [°]'); ax.set_ylabel('Sonnenhöhe [°]')
            annotation = f"Sky View Factor: {svf:.2f}"
            ax.text(0.01, 0.99, annotation, transform=ax.transAxes, ha='left', va='top', fontsize=8)

            ax.set_xticks(np.arange(0,361,45))
            ax.set_yticks(np.arange(0,91,10))
            ax.margins(y=0.05)

            # Stundenlinien für wahre Ortszeit
            z0 = horizon_df['hoehe_standort'].iloc[0]
            x, y = coords
            # Koordinatentransform LV95 -> WGS84
            crs_src = QgsCoordinateReferenceSystem('EPSG:2056')
            crs_dest = QgsCoordinateReferenceSystem('EPSG:4326')
            transformer = QgsCoordinateTransform(crs_src, crs_dest, QgsProject.instance())
            pt = transformer.transform(x, y)
            lon, lat = pt.x(), pt.y()

            for civil_hour in range(0, 24):
                # Erzeuge UTC-Datum (wir interpretieren civil_hour als UTC – SPA macht den Lon-Offset selbst)
                dt_utc = datetime(year, 1, 1, civil_hour, tzinfo=timezone.utc)  # Dummy-Datum zum Initialisieren
                azs, els, lsts = [], [], []
                for m in [1,2,3,4,5,6,12]:
                    dt_utc = datetime(year, m, 21, civil_hour, tzinfo=timezone.utc)
                    az, el, lst = spa_calculate(dt_utc, lat, lon, z0, return_lst=True)
                    azs.append(az); els.append(el); lsts.append(lst)

                azs = np.array(azs); els = np.array(els); lsts = np.array(lsts)
                mask = els >= 0
                if not mask.any():
                    continue

                # oberhalb Horizont
                ax.plot(azs[mask], els[mask], linestyle='-', color='darkgrey', linewidth=0.5)

                # Label an der höchsten sichtbaren Stelle
                idx = np.argmax(els[mask])
                az_label = azs[mask][idx]
                el_label = els[mask][idx]

                # Stunden und Minuten aus LST erzeugen
                sh = int(solar_time)
                sm = int((solar_time - sh) * 60 + 0.5)
                label = f"{sh:02d}:{sm:02d}"
                ax.text(
                    az_label, el_label + 2,
                    label, color='gray', fontsize=8,
                    ha='center', va='bottom', clip_on=False
                )

            fig.tight_layout()
            # Speichern mit dem in __init__ gesetzten Prefix und out_dir
            png_name = f"{self.prefix}_horizont_sonnenbahn_gesamt.png"
            png = os.path.join(self.out_dir, png_name)
            fig.savefig(png, dpi=300)
            plt.close(fig)

        except Exception as e:
            QgsMessageLog.logMessage(f"Plot-Fehler: {e}", "HorSunView", Qgis.Critical)