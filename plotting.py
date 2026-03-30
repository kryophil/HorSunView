# -*- coding: utf-8 -*-
"""
plotting.py – Sonnenstanddiagramm, monochromes Design (kaltluftseen.ch-Stil).

Architektur: 4 Phasen
  Phase 1 – Achsen, Horizont, Kurven (ohne Text-Labels)
  Phase 2 – tight_layout() + canvas.draw() → genaue Transform
  Phase 3 – Text-Labels (Monate, Stunden, SVF, Copyright)
  Phase 4 – Speichern
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import os
from datetime import datetime, timezone, timedelta

from .spa_nrel import spa_calculate
from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsProject, QgsMessageLog, Qgis
)

# ── Schriftart-Erkennung ──────────────────────────────────────────────────────
def _find_font(preferred):
    """Gibt die erste verfügbare Schriftfamilie aus der Liste zurück."""
    available = {f.name for f in fm.fontManager.ttflist}
    for family in preferred:
        if family in available:
            return family
    return 'DejaVu Sans'

_FONT_AXES = _find_font(['Calibri', 'DejaVu Sans'])   # Achsentitel, Ticks
_FONT_DATA = _find_font(['Arial', 'DejaVu Sans'])      # Monats- und Stunden-Labels

# ── Designkonstanten ──────────────────────────────────────────────────────────
_BLACK     = '#000000'
_DARKGREY  = '#444444'
_MIDGREY   = '#888888'
_LIGHTGREY = '#BBBBBB'
_FILLGREY  = '#c0c0c0'
_SUNPATH_C = '#606060'   # Monatskurven (hinter Horizont sichtbar)
_HOUR_C    = '#909090'   # Stundenlinien (hinter Horizont sichtbar)

_LW_HORIZON = 2.8    # Horizontlinie
_LW_MONTH   = 1.1    # Monatskurven
_LW_HOUR    = 0.55   # Stundenlinien
_LW_GRID    = 0.4    # Gitternetz

_FS_TITLE   = 13
_FS_AXLABEL = 11
_FS_TICK    = 10
_FS_MONTH   = 10
_FS_HOUR    = 9
_FS_SVF     = 10
_FS_COPY    = 8

_DEC_KEY    = "21. Dez"


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _label_pos_in_range(df, az_lo=150, az_hi=200):
    """
    Gibt (az, el) der flachsten Stelle der Kurve in [az_lo, az_hi] zurück.
    Fallback: höchster sichtbarer Punkt.
    """
    visible = df[df['höhe'] >= 0]
    if visible.empty:
        return None, None

    sub = visible[(visible['azimut'] >= az_lo) & (visible['azimut'] <= az_hi)]
    if len(sub) < 3:
        idx = visible['höhe'].idxmax()
        return float(visible.at[idx, 'azimut']), float(visible.at[idx, 'höhe'])

    azs = sub['azimut'].values
    els = sub['höhe'].values
    grad = np.abs(np.gradient(els, azs))
    i = int(np.argmin(grad))
    return float(azs[i]), float(els[i])


def _tangent_angle(ax, df, az_center, window_deg=10):
    """
    Rotationswinkel (Grad) tangential zur Kurve an az_center.
    Berechnet nach canvas.draw() für genaue Transform.
    """
    nearby = df[
        (df['azimut'] >= az_center - window_deg) &
        (df['azimut'] <= az_center + window_deg) &
        (df['höhe'] >= 0)
    ]
    if len(nearby) < 2:
        return 0.0
    az1 = float(nearby['azimut'].iloc[0])
    el1 = float(nearby['höhe'].iloc[0])
    az2 = float(nearby['azimut'].iloc[-1])
    el2 = float(nearby['höhe'].iloc[-1])
    try:
        p1 = ax.transData.transform([az1, el1])
        p2 = ax.transData.transform([az2, el2])
        return float(np.degrees(np.arctan2(p2[1] - p1[1], p2[0] - p1[0])))
    except Exception:
        return 0.0


# ── Hauptklasse ───────────────────────────────────────────────────────────────

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
        coords     : (x, y)         LV95-Koordinaten
        year       : int
        place      : str            Ortsname für Titel
        """
        try:
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.set_facecolor('white')
            fig.patch.set_facecolor('white')

            # ── Phase 1: Achsen, Linien, Flächen ─────────────────────────────

            # Achsen-Grenzen
            ax.set_xlim(0, 360)
            ax.set_ylim(0, 90)

            # X-Achse
            ax.set_xticks(np.arange(0, 361, 45))
            ax.set_xticklabels(
                ['0', '45', '90', '135', '180', '225', '270', '315', '360']
            )
            for lbl in ax.get_xticklabels():
                lbl.set_fontfamily(_FONT_AXES)
                lbl.set_fontsize(_FS_TICK)
            ax.set_xlabel('Azimut °', fontsize=_FS_AXLABEL, fontfamily=_FONT_AXES)

            # Y-Achse
            ax.set_yticks(np.arange(0, 91, 10))
            ax.set_yticklabels([str(v) for v in range(0, 91, 10)])
            for lbl in ax.get_yticklabels():
                lbl.set_fontfamily(_FONT_AXES)
                lbl.set_fontsize(_FS_TICK)
            ax.set_ylabel('Sonnenhöhe °', fontsize=_FS_AXLABEL, fontfamily=_FONT_AXES)

            # Titel
            title = f"Sonnenstanddiagramm {place}".strip()
            ax.set_title(
                title, fontsize=_FS_TITLE,
                fontweight='normal', color=_BLACK, fontfamily=_FONT_AXES
            )

            # 4-seitiger Rahmen (alle Spines sichtbar, oben/rechts ohne Ticks)
            for spine in ax.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(0.8)
                spine.set_color(_BLACK)
            ax.tick_params(which='both', top=False, right=False)

            # Gitternetz
            ax.grid(
                True, linestyle='--', linewidth=_LW_GRID,
                color=_LIGHTGREY, zorder=0
            )

            # Horizont (zorder 3/4 → überdeckt Sonnenbahnen und Stundenlinien)
            ax.fill_between(
                horizon_df['azimut'], horizon_df['horizontwinkel'],
                y2=0, color=_FILLGREY, alpha=0.85, zorder=3
            )
            ax.plot(
                horizon_df['azimut'], horizon_df['horizontwinkel'],
                color=_BLACK, linewidth=_LW_HORIZON, zorder=4
            )

            # Stundenlinien (nur Linien, Labels später)
            hour_label_data = self._draw_hour_lines(ax, horizon_df, coords, year)

            # Monatskurven (nur Linien, Labels später)
            month_label_data = []   # [(az, el, lbl, df), ...]
            for lbl, df in sun_paths.items():
                visible = df[df['höhe'] >= 0]
                if visible.empty:
                    continue
                ax.plot(
                    df['azimut'], df['höhe'],
                    linestyle='-', color=_SUNPATH_C,
                    linewidth=_LW_MONTH, zorder=2
                )
                az_lbl, el_lbl = _label_pos_in_range(df)
                if az_lbl is not None:
                    month_label_data.append((az_lbl, el_lbl, lbl, df))

            # ── Phase 2: Layout finalisieren für genaue Transforms ───────────
            fig.tight_layout()
            fig.canvas.draw()

            # ── Phase 3: Text-Labels ─────────────────────────────────────────

            # Monats-Labels (tangential zur Kurve)
            for az, el, lbl, df in month_label_data:
                rot = _tangent_angle(ax, df, az)
                ax.text(
                    az, el + 0.5, lbl,
                    rotation=rot, rotation_mode='anchor',
                    ha='center', va='bottom',
                    fontsize=_FS_MONTH, fontfamily=_FONT_DATA,
                    color=_BLACK, clip_on=True, zorder=6
                )

            # Stunden-Labels: untere Ecke der Textbox nahe Berührungspunkt mit Jun-Kurve
            # az < 180° → untere rechte Ecke (ha='right')
            # az ≥ 180° → untere linke Ecke (ha='left')
            for az, el, label in hour_label_data:
                ha = 'right' if az < 180.0 else 'left'
                ax.text(
                    az, el + 1.2, label,
                    ha=ha, va='bottom',
                    fontsize=_FS_HOUR, fontfamily=_FONT_DATA,
                    color=_MIDGREY, clip_on=True, zorder=6
                )

            # Sky View Factor
            ax.text(
                0.01, 0.99,
                f"Sky View Factor: {svf:.2f}",
                transform=ax.transAxes, ha='left', va='top',
                fontsize=_FS_SVF, fontfamily=_FONT_AXES
            )

            # Copyright
            ax.text(
                0.99, 0.01,
                '© Geodaten: swisstopo\nGraphik: kaltluftseen.ch',
                transform=ax.transAxes, ha='right', va='bottom',
                fontsize=_FS_COPY, fontfamily=_FONT_AXES,
                color=_BLACK, linespacing=1.5
            )

            # ── Phase 4: Speichern ────────────────────────────────────────────
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
        Zeichnet UTC-Stundenlinien (~365 Punkte pro Linie, NaN für unsichtbare Tage).
        Label-Ankerpunkt = Berührungspunkt der Linie mit der Jun-21-Sonnenbahn.
        Gibt Liste von (az_touch, el_touch, label_text) für Phase 3 zurück.
        """
        x0, y0 = coords
        z0 = horizon_df['hoehe_standort'].iloc[0]

        crs_src = QgsCoordinateReferenceSystem('EPSG:2056')
        crs_dst = QgsCoordinateReferenceSystem('EPSG:4326')
        transformer = QgsCoordinateTransform(crs_src, crs_dst, QgsProject.instance())
        pt = transformer.transform(x0, y0)
        lon, lat = pt.x(), pt.y()

        label_data = []
        n_days = 365

        for utc_hour in range(0, 24):
            azs = np.empty(n_days)
            els = np.empty(n_days)

            for day_num in range(n_days):
                dt_utc = (
                    datetime(year, 1, 1, utc_hour, 0, tzinfo=timezone.utc)
                    + timedelta(days=day_num)
                )
                az, el = spa_calculate(dt_utc, lat, lon, z0)
                azs[day_num] = az
                els[day_num] = el

            mask = els >= 0
            if not mask.any():
                continue

            # NaN für unsichtbare Tage → saubere Lücken statt Verbindungslinien
            azs_plot = azs.copy()
            els_plot = els.copy()
            azs_plot[~mask] = np.nan
            els_plot[~mask] = np.nan

            ax.plot(
                azs_plot, els_plot,
                linestyle='--', color=_HOUR_C,
                linewidth=_LW_HOUR, zorder=1
            )

            # Berührungspunkt mit 21. Juni (höchste Sonnenbahn)
            dt_june21 = datetime(year, 6, 21, utc_hour, 0, tzinfo=timezone.utc)
            az_touch, el_touch = spa_calculate(dt_june21, lat, lon, z0)

            if el_touch < 0:
                # Fallback: Punkt mit höchster Elevation auf der sichtbaren Linie
                idx = int(np.argmax(np.where(mask, els, -np.inf)))
                az_touch = float(azs[idx])
                el_touch = float(els[idx])

            label_data.append((float(az_touch), float(el_touch), f"{utc_hour:02d} UTC"))

        return label_data
