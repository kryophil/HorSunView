# -*- coding: utf-8 -*-
"""
plotting.py – Sonnenstanddiagramm, monochromes Design (kaltluftseen.ch-Stil).

Design:
  - Vollständig monochrom (schwarz / dunkelgrau / hellgrau)
  - X-Achse: 0°–360° mit numerischen Grad-Labels, Titel «Azimut °»
  - Y-Achse: 0°–90°, Titel «Sonnenhöhe °»
  - Stundenlinien in UTC, Labels «6 UTC», «7 UTC» usw.
  - Copyright-Vermerk unten rechts
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

# ── Designkonstanten ──────────────────────────────────────────────────────────
_BLACK      = '#000000'
_DARKGREY   = '#444444'
_MIDGREY    = '#888888'
_LIGHTGREY  = '#cccccc'
_FILLGREY   = '#bbbbbb'

_LW_HORIZON = 2.8   # Horizontlinie
_LW_DEC     = 1.5   # Dezember-Kurve
_LW_MONTH   = 1.0   # übrige Monatskurven
_LW_HOUR    = 0.5   # Stundenlinien

_FS_TITLE   = 13
_FS_AXLABEL = 11
_FS_TICK    = 10
_FS_MONTH   = 10
_FS_HOUR    = 9
_FS_SVF     = 10
_FS_COPY    = 8

_DEC_KEY    = "21. Dez"   # muss mit analysis.py übereinstimmen


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
            ax.set_facecolor('white')
            fig.patch.set_facecolor('white')

            # ── Achsen ────────────────────────────────────────────────────────
            ax.set_xlim(0, 360)
            ax.set_ylim(0, 90)

            ax.set_xticks(np.arange(0, 361, 45))
            ax.set_xticklabels(
                ['0', '45', '90', '135', '180', '225', '270', '315', '360'],
                fontsize=_FS_TICK
            )
            ax.set_xlabel('Azimut °', fontsize=_FS_AXLABEL)

            ax.set_yticks(np.arange(0, 91, 10))
            ax.set_yticklabels(
                [str(v) for v in range(0, 91, 10)],
                fontsize=_FS_TICK
            )
            ax.set_ylabel('Sonnenhöhe °', fontsize=_FS_AXLABEL)

            # ── Titel ─────────────────────────────────────────────────────────
            title = f"Sonnenstanddiagramm {place}".strip()
            ax.set_title(
                title, fontsize=_FS_TITLE, fontweight='normal', color=_BLACK
            )

            # ── Gitternetz ────────────────────────────────────────────────────
            ax.grid(
                True, linestyle='--', linewidth=0.4,
                color=_LIGHTGREY, zorder=0
            )

            # ── Horizontprofil ────────────────────────────────────────────────
            ax.fill_between(
                horizon_df['azimut'], horizon_df['horizontwinkel'],
                y2=0, color=_FILLGREY, alpha=0.85, zorder=2
            )
            ax.plot(
                horizon_df['azimut'], horizon_df['horizontwinkel'],
                color=_BLACK, linewidth=_LW_HORIZON, zorder=3
            )

            # ── Stundenlinien (UTC) ───────────────────────────────────────────
            # Vor den Sonnenbahnen zeichnen (zorder=1), damit sie darunter liegen
            self._draw_hour_lines(ax, horizon_df, coords, year)

            # ── Sonnenbahnen (alle ausser Dezember) ───────────────────────────
            for lbl, df in sun_paths.items():
                if lbl == _DEC_KEY:
                    continue
                visible = df[df['höhe'] >= 0]
                if visible.empty:
                    continue
                ax.plot(
                    df['azimut'], df['höhe'],
                    linestyle='-', color=_DARKGREY,
                    linewidth=_LW_MONTH, zorder=4
                )
                idx_max = df['höhe'].idxmax()
                ax.text(
                    df.at[idx_max, 'azimut'], df.at[idx_max, 'höhe'] + 1.5,
                    lbl, fontsize=_FS_MONTH, ha='center', va='bottom',
                    color=_BLACK, clip_on=True
                )

            # ── Dezember (obenauf, etwas dicker) ─────────────────────────────
            if _DEC_KEY in sun_paths:
                df = sun_paths[_DEC_KEY]
                visible = df[df['höhe'] >= 0]
                if not visible.empty:
                    ax.plot(
                        df['azimut'], df['höhe'],
                        linestyle='-', color=_BLACK,
                        linewidth=_LW_DEC, zorder=5
                    )
                    idx_max = df['höhe'].idxmax()
                    ax.text(
                        df.at[idx_max, 'azimut'], df.at[idx_max, 'höhe'] + 1.5,
                        _DEC_KEY, fontsize=_FS_MONTH, ha='center', va='bottom',
                        color=_BLACK, clip_on=True
                    )

            # ── Sky View Factor ───────────────────────────────────────────────
            ax.text(
                0.01, 0.99,
                f"Sky View Factor: {svf:.2f}",
                transform=ax.transAxes, ha='left', va='top',
                fontsize=_FS_SVF,
                bbox=dict(
                    boxstyle='round,pad=0.3',
                    fc='white', ec=_LIGHTGREY, alpha=0.9
                )
            )

            # ── Copyright ─────────────────────────────────────────────────────
            ax.text(
                0.99, 0.01,
                '© Geodaten: swisstopo\nGraphik: kaltluftseen.ch',
                transform=ax.transAxes, ha='right', va='bottom',
                fontsize=_FS_COPY, color=_MIDGREY, linespacing=1.5
            )

            fig.tight_layout()
            png_name = f"{self.prefix}_horizont_sonnenbahn_gesamt.png"
            png_path = os.path.join(self.out_dir, png_name)
            fig.savefig(png_path, dpi=300, facecolor='white')
            plt.close(fig)
            QgsMessageLog.logMessage(
                f"Plot gespeichert: {png_path}", "HorSunView", Qgis.Info
            )

        except Exception as e:
            plt.close('all')
            QgsMessageLog.logMessage(
                f"Plot-Fehler: {e}", "HorSunView", Qgis.Critical
            )
            raise

    def _draw_hour_lines(self, ax, horizon_df, coords, year):
        """
        Zeichnet UTC-Stundenlinien als gestrichelte Linien.
        Labels: «6 UTC», «7 UTC», ..., «18 UTC».
        """
        x0, y0 = coords
        z0 = horizon_df['hoehe_standort'].iloc[0]

        crs_src = QgsCoordinateReferenceSystem('EPSG:2056')
        crs_dst = QgsCoordinateReferenceSystem('EPSG:4326')
        transformer = QgsCoordinateTransform(crs_src, crs_dst, QgsProject.instance())
        pt = transformer.transform(x0, y0)
        lon, lat = pt.x(), pt.y()

        ref_months = [1, 2, 3, 4, 5, 6, 12]

        for utc_hour in range(0, 24):
            azs, els = [], []
            for m in ref_months:
                dt_utc = datetime(year, m, 21, utc_hour, 0, tzinfo=timezone.utc)
                az, el = spa_calculate(dt_utc, lat, lon, z0)
                azs.append(az)
                els.append(el)

            azs = np.array(azs)
            els = np.array(els)
            mask = els >= 0

            if not mask.any():
                continue

            ax.plot(
                azs[mask], els[mask],
                linestyle='--', color=_LIGHTGREY,
                linewidth=_LW_HOUR, zorder=1
            )

            # Label an der höchsten sichtbaren Stelle
            idx = np.argmax(els[mask])
            az_label = azs[mask][idx]
            el_label = els[mask][idx]
            ax.text(
                az_label, el_label + 1.0,
                f"{utc_hour} UTC",
                color=_MIDGREY, fontsize=_FS_HOUR,
                ha='center', va='bottom', clip_on=True
            )
