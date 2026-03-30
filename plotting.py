# -*- coding: utf-8 -*-
"""
plotting.py – Sonnenstanddiagramm mit Horizontlinie und Stundenlinien.

Korrekturen gegenüber Originalversion:
  - solar_time → lst (NameError behoben)
  - Dezember-Kurve wird nicht mehr in jedem Loop-Durchlauf neu gezeichnet
  - Stundenlinien: UTC-Stunde korrekt in Lokalzeit (Sonnenstunden) umgerechnet
  - iface-Abhängigkeit entfernt (Fehlerhandling via Exception)
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os
from datetime import datetime, timezone

from .spa_nrel import spa_calculate
from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsProject, QgsMessageLog, Qgis
)


class Plotter:
    def __init__(self, prefix, out_dir):
        self.prefix = prefix
        self.out_dir = out_dir

    def plot_and_save(self, horizon_df, svf, sun_paths, coords, year, place):
        """
        Erstellt das Sonnenstanddiagramm und speichert es als PNG.

        Parameters
        ----------
        horizon_df : pd.DataFrame   Spalten: azimut, horizontwinkel, hoehe_standort
        svf        : float          Sky View Factor
        sun_paths  : dict           {label: DataFrame mit azimut, höhe}
        coords     : (x, y)         LV95-Koordinaten des Standorts
        year       : int
        place      : str            Ortsname für Titel
        """
        try:
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.set_xlim(0, 360)
            ax.set_ylim(-5, 90)
            ax.set_xticks(np.arange(0, 361, 45))
            ax.set_yticks(np.arange(0, 91, 10))
            ax.set_xticklabels(['N', 'NO', 'O', 'SO', 'S', 'SW', 'W', 'NW', 'N'])
            ax.grid(True, linestyle='--', linewidth=0.4, color='lightgrey')
            ax.set_xlabel('Azimut')
            ax.set_ylabel('Sonnenhöhe / Horizontwinkel [°]')
            title = f"Sonnenstanddiagramm {place}" if place else "Sonnenstanddiagramm"
            ax.set_title(title)

            # --- Horizontprofil ---
            ax.fill_between(
                horizon_df['azimut'], horizon_df['horizontwinkel'],
                color='sienna', alpha=0.25, label='Horizont'
            )
            ax.plot(
                horizon_df['azimut'], horizon_df['horizontwinkel'],
                color='saddlebrown', linewidth=1.5
            )

            # --- Sonnenbahnen ---
            # Alle Kurven ausser Dezember zuerst zeichnen
            for lbl, df in sun_paths.items():
                if lbl == "21. Dez.":
                    continue
                visible = df[df['höhe'] >= 0]
                if visible.empty:
                    continue
                ax.plot(
                    df['azimut'], df['höhe'],
                    linestyle='-', color='orangered', linewidth=0.9
                )
                idx_max = df['höhe'].idxmax()
                ax.text(
                    df.at[idx_max, 'azimut'], df.at[idx_max, 'höhe'] + 1.5,
                    lbl, fontsize=7.5, ha='center', va='bottom',
                    color='orangered', clip_on=True
                )

            # Dezember zum Schluss (dicker, damit er obenauf liegt)
            if "21. Dez." in sun_paths:
                df = sun_paths["21. Dez."]
                ax.plot(
                    df['azimut'], df['höhe'],
                    linestyle='-', color='navy', linewidth=1.5
                )
                idx_max = df['höhe'].idxmax()
                ax.text(
                    df.at[idx_max, 'azimut'], df.at[idx_max, 'höhe'] + 1.5,
                    "21. Dez.", fontsize=7.5, ha='center', va='bottom',
                    color='navy', clip_on=True
                )

            # --- Stundenlinien (wahre Ortszeit) ---
            self._draw_hour_lines(ax, horizon_df, coords, year)

            # --- SVF-Annotation ---
            ax.text(
                0.01, 0.99,
                f"Sky View Factor: {svf:.3f}",
                transform=ax.transAxes, ha='left', va='top',
                fontsize=9, bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.7)
            )

            fig.tight_layout()
            png_name = f"{self.prefix}_horizont_sonnenbahn_gesamt.png"
            png_path = os.path.join(self.out_dir, png_name)
            fig.savefig(png_path, dpi=300)
            plt.close(fig)
            QgsMessageLog.logMessage(
                f"Plot gespeichert: {png_path}", "HorSunView", Qgis.Info
            )

        except Exception as e:
            plt.close('all')
            QgsMessageLog.logMessage(
                f"Plot-Fehler: {e}", "HorSunView", Qgis.Critical
            )
            raise  # damit run() den Fehler fängt

    def _draw_hour_lines(self, ax, horizon_df, coords, year):
        """
        Zeichnet Stundenlinien der wahren Ortszeit (Solar Time).

        Für jeden UTC-Stundenwert werden Azimut/Elevation am 21. jedes
        Monats berechnet. Der LST-Wert (local solar time) aus spa_calculate
        wird für das Label verwendet.
        """
        x0, y0 = coords
        z0 = horizon_df['hoehe_standort'].iloc[0]

        # LV95 → WGS84
        crs_src = QgsCoordinateReferenceSystem('EPSG:2056')
        crs_dst = QgsCoordinateReferenceSystem('EPSG:4326')
        transformer = QgsCoordinateTransform(crs_src, crs_dst, QgsProject.instance())
        pt = transformer.transform(x0, y0)
        lon, lat = pt.x(), pt.y()

        ref_months = [1, 2, 3, 4, 5, 6, 12]

        for utc_hour in range(0, 24):
            azs, els, lsts = [], [], []
            for m in ref_months:
                dt_utc = datetime(year, m, 21, utc_hour, 0, tzinfo=timezone.utc)
                az, el, lst = spa_calculate(dt_utc, lat, lon, z0, return_lst=True)
                azs.append(az)
                els.append(el)
                lsts.append(lst)

            azs = np.array(azs)
            els = np.array(els)
            lsts = np.array(lsts)
            mask = els >= 0

            if not mask.any():
                continue

            ax.plot(
                azs[mask], els[mask],
                linestyle=':', color='grey', linewidth=0.5, zorder=1
            )

            # Label an der höchsten sichtbaren Stelle
            idx = np.argmax(els[mask])
            az_label = azs[mask][idx]
            el_label = els[mask][idx]
            lst_val = lsts[mask][idx]   # ← KORREKTUR: war 'solar_time' (NameError)

            sh = int(lst_val)
            sm = int((lst_val - sh) * 60 + 0.5)
            label = f"{sh:02d}:{sm:02d}"
            ax.text(
                az_label, el_label + 1.0,
                label, color='grey', fontsize=7,
                ha='center', va='bottom', clip_on=True
            )
