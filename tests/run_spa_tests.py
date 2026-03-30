# -*- coding: utf-8 -*-
"""
Unit-Tests für HorSunView.

Getestete Bereiche:
  1. SVF-Berechnung mit synthetischem Horizontprofil
  2. SPA-Werte gegen den NREL-Referenzfall
     (17. Oktober 2003, 12:30:30 MST, Golden/Colorado)
  3. Vorzeichen und Wertebereich von Azimut (0–360°) und Elevation (−90° bis +90°)

Ausführen (ohne QGIS):
    python -m pytest tests/run_spa_tests.py -v
oder direkt:
    python tests/run_spa_tests.py
"""
import sys
import os
import math
import unittest

# Plugin-Verzeichnis zum Suchpfad hinzufügen, damit spa_strict ohne
# relative Imports importierbar ist.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spa_strict import SpaData, spa_calculate, SPA_ZA  # noqa: E402


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _make_spa(year, month, day, hour, minute, second,
              lat, lon, elevation_m, pressure_mbar, temperature_c,
              delta_t, delta_ut1=0.0, timezone=0.0):
    """Erstellt ein SpaData-Objekt und führt spa_calculate() aus.

    Parameters
    ----------
    timezone : float
        Nur für die interne SPA-Berechnung relevant, wenn SPA_ZA_RTS
        verwendet wird. Bei SPA_ZA immer 0.0 übergeben (UTC-Eingabe).

    Returns
    -------
    (rc, spa) – Rückgabecode (0 = OK) und gefülltes SpaData-Objekt.
    """
    spa = SpaData(
        year=int(year), month=int(month), day=int(day),
        hour=int(hour), minute=int(minute), second=float(second),
        delta_ut1=float(delta_ut1),
        delta_t=float(delta_t),
        timezone=float(timezone),
        longitude=float(lon),
        latitude=float(lat),
        elevation=float(elevation_m),
        pressure=float(pressure_mbar),
        temperature=float(temperature_c),
        slope=0.0,
        azm_rotation=0.0,
        atmos_refract=0.5667,
        function=SPA_ZA,
    )
    rc = spa_calculate(spa)
    return rc, spa


def _compute_svf(horizon_angles_deg):
    """Repliziert compute_svf() aus analysis.py.

    Parameters
    ----------
    horizon_angles_deg : list[float]
        361 Horizontwinkel (0°…360°, wobei 360°-Wert = Schlusspunkt für
        Closure) in Grad. Der letzte Wert wird wie in analysis.py
        weggelassen, um Doppelzählung zu vermeiden.

    Returns
    -------
    float  Sky View Factor im Bereich [0, 1].
    """
    beta = [math.radians(a) for a in horizon_angles_deg[:-1]]  # 360 Werte
    n = len(beta)
    dtheta = 2 * math.pi / n
    return (1.0 / (2.0 * math.pi)) * sum(math.cos(b) ** 2 * dtheta for b in beta)


# ---------------------------------------------------------------------------
# 1. SVF-Berechnung
# ---------------------------------------------------------------------------

class TestSVF(unittest.TestCase):
    """SVF-Berechnung mit synthetischem Horizontprofil."""

    def _uniform_horizon(self, angle_deg):
        """Gibt ein Profil zurück, bei dem alle 361 Richtungen gleich sind."""
        return [float(angle_deg)] * 361

    def test_flat_horizon_svf_is_one(self):
        """Flacher Horizont (0°) → SVF = 1.0."""
        svf = _compute_svf(self._uniform_horizon(0.0))
        self.assertAlmostEqual(svf, 1.0, places=9,
                               msg="Flacher Horizont muss SVF = 1.0 ergeben")

    def test_full_obstruction_svf_is_zero(self):
        """Vollständige Abschirmung (90°) → SVF = 0.0."""
        svf = _compute_svf(self._uniform_horizon(90.0))
        self.assertAlmostEqual(svf, 0.0, places=9,
                               msg="Vollständige Abschirmung muss SVF = 0.0 ergeben")

    def test_uniform_30deg_svf(self):
        """Einheitlicher Horizont bei 30° → SVF = cos²(30°) ≈ 0.75."""
        svf = _compute_svf(self._uniform_horizon(30.0))
        expected = math.cos(math.radians(30.0)) ** 2
        self.assertAlmostEqual(svf, expected, places=6,
                               msg=f"SVF bei 30°-Horizont soll ≈ {expected:.6f} sein")

    def test_svf_bounds_for_various_angles(self):
        """SVF muss für beliebige einheitliche Horizontwinkel in [0, 1] liegen."""
        for angle in range(0, 91, 5):
            svf = _compute_svf(self._uniform_horizon(float(angle)))
            self.assertGreaterEqual(svf, 0.0,
                                    msg=f"SVF < 0 bei Horizontwinkel {angle}°")
            self.assertLessEqual(svf, 1.0,
                                 msg=f"SVF > 1 bei Horizontwinkel {angle}°")

    def test_svf_decreases_monotonically(self):
        """SVF muss mit steigendem Horizontwinkel monoton abnehmen."""
        angles = list(range(0, 91, 10))
        svfs = [_compute_svf(self._uniform_horizon(float(a))) for a in angles]
        for i in range(len(svfs) - 1):
            self.assertGreaterEqual(
                svfs[i], svfs[i + 1],
                msg=f"SVF bei {angles[i]}° ({svfs[i]:.4f}) soll ≥ "
                    f"SVF bei {angles[i+1]}° ({svfs[i+1]:.4f}) sein"
            )


# ---------------------------------------------------------------------------
# 2. SPA gegen NREL-Referenzfall
# ---------------------------------------------------------------------------

class TestSPANRELReference(unittest.TestCase):
    """
    Verifikation gegen den NREL-Referenzfall aus Reda & Andreas (2004/2008):

        Datum  : 17. Oktober 2003, 12:30:30 MST (UTC-7) = 19:30:30 UTC
        Ort    : Golden, Colorado, USA
                 lat = 39.742476°N, lon = −105.1786°W
                 Elevation = 1830.14 m
        Meteo  : Druck = 820 mbar, Temperatur = 11 °C
        ΔT     = 67.0 s, ΔUT1 = 0 s

    Referenzwerte (Topozentrisch, mit Refraktion):
        Zenitwinkel  = 50.1116°
        Azimut       = 194.3397°
        Elevation e  = 39.888°   (= 90° − Zenitwinkel, inkl. Refraktion)
    """

    # Toleranzen
    ZENITH_TOL = 0.002  # °
    AZ_TOL = 0.002      # °
    EL_TOL = 0.010      # °

    @classmethod
    def setUpClass(cls):
        rc, cls.spa = _make_spa(
            year=2003, month=10, day=17,
            hour=19, minute=30, second=30.0,   # UTC
            lat=39.742476, lon=-105.1786,
            elevation_m=1830.14,
            pressure_mbar=820.0, temperature_c=11.0,
            delta_t=67.0, delta_ut1=0.0,
        )
        cls.rc = rc

    def test_spa_returns_no_error(self):
        """spa_calculate() muss Rückgabecode 0 (kein Fehler) liefern."""
        self.assertEqual(self.rc, 0,
                         f"SPA-Fehlercode {self.rc} erwartet: 0")

    def test_zenith_angle(self):
        """Zenitwinkel: NREL-Referenz 50.1116° (±{self.ZENITH_TOL}°)."""
        self.assertAlmostEqual(
            self.spa.zenith, 50.1116, delta=self.ZENITH_TOL,
            msg=f"Zenitwinkel {self.spa.zenith:.4f}° weicht zu stark vom "
                f"Referenzwert 50.1116° ab"
        )

    def test_azimuth(self):
        """Azimut: NREL-Referenz 194.3397° (±{self.AZ_TOL}°)."""
        self.assertAlmostEqual(
            self.spa.azimuth, 194.3397, delta=self.AZ_TOL,
            msg=f"Azimut {self.spa.azimuth:.4f}° weicht zu stark vom "
                f"Referenzwert 194.3397° ab"
        )

    def test_elevation(self):
        """Elevation (inkl. Refraktion): NREL-Referenz 39.888° (±{self.EL_TOL}°)."""
        self.assertAlmostEqual(
            self.spa.e, 39.888, delta=self.EL_TOL,
            msg=f"Elevation {self.spa.e:.4f}° weicht zu stark vom "
                f"Referenzwert 39.888° ab"
        )

    def test_zenith_elevation_sum(self):
        """zenith + e (beide refraktionskorrigiert) müssen exakt 90° ergeben."""
        # spa.zenith wird als 90° − spa.e definiert (topocentric_zenith_angle)
        total = self.spa.zenith + self.spa.e
        self.assertAlmostEqual(
            total, 90.0, delta=1e-9,
            msg=f"zenith + e = {total:.9f}° ≠ 90°"
        )


# ---------------------------------------------------------------------------
# 3. Wertebereich Azimut und Elevation
# ---------------------------------------------------------------------------

class TestAzimuthElevationRanges(unittest.TestCase):
    """Azimut ∈ [0°, 360°] und Elevation ∈ [−90°, +90°] für diverse Standorte."""

    # (year, month, day, hour_utc, min, lat, lon, elev, pres, temp, dt)
    TEST_CASES = [
        # Schweiz – Sommermittag
        (2024, 6, 21, 10, 0, 47.37, 8.54, 408, 1013.25, 20.0, 69),
        # Schweiz – Wintersonnenwende Mittag
        (2024, 12, 21, 11, 0, 47.37, 8.54, 408, 1013.25,  0.0, 69),
        # Schweiz – Morgen
        (2024, 3, 21,  6, 0, 47.37, 8.54, 408, 1013.25, 10.0, 69),
        # Schweiz – Abend
        (2024, 9, 21, 16, 0, 47.37, 8.54, 408, 1013.25, 15.0, 69),
        # Schweiz – Mitternacht (Sonne unter Horizont)
        (2024, 6, 21,  0, 0, 47.37, 8.54, 408, 1013.25, 15.0, 69),
        # Norwegen – Mittsommer (Mitternachtssonne möglich)
        (2024, 6, 21, 12, 0, 70.0,  25.0,   0, 1013.25,  5.0, 69),
        # Sydney – Südhalbkugel-Winter
        (2024, 12, 21, 12, 0, -33.87, 151.21, 50, 1013.25, 25.0, 69),
        # Äquator – Tagundnachtgleiche
        (2024, 3, 21, 12, 0,  0.0,   0.0,    0, 1013.25, 25.0, 69),
    ]

    def _spa(self, tc):
        yr, mo, dy, hr, mi, lat, lon, elev, pres, temp, dt = tc
        return _make_spa(yr, mo, dy, hr, mi, 0.0, lat, lon, elev, pres, temp, dt)

    def test_azimuth_in_range(self):
        """Azimut muss stets in [0°, 360°] liegen."""
        for tc in self.TEST_CASES:
            rc, spa = self._spa(tc)
            self.assertEqual(rc, 0, msg=f"SPA-Fehler für Testfall {tc[:4]}")
            self.assertGreaterEqual(spa.azimuth, 0.0,
                                    msg=f"Azimut < 0° bei {tc}")
            self.assertLessEqual(spa.azimuth, 360.0,
                                 msg=f"Azimut > 360° bei {tc}")

    def test_elevation_in_range(self):
        """Elevation muss stets in [−90°, +90°] liegen."""
        for tc in self.TEST_CASES:
            rc, spa = self._spa(tc)
            self.assertEqual(rc, 0, msg=f"SPA-Fehler für Testfall {tc[:4]}")
            self.assertGreaterEqual(spa.e, -90.0,
                                    msg=f"Elevation < −90° bei {tc}")
            self.assertLessEqual(spa.e, 90.0,
                                 msg=f"Elevation > +90° bei {tc}")

    def test_noon_sun_south_in_switzerland(self):
        """Sonnenhöchststand in der Schweiz: Sonne steht südlich des Zenits (Azimut ~180°)."""
        # 21. Juni, 11:30 UTC ≈ solar noon in Zürich (lon=8.54° → Offset ~34 min)
        rc, spa = _make_spa(2024, 6, 21, 11, 30, 0.0, 47.37, 8.54,
                            408, 1013.25, 20.0, 69)
        self.assertEqual(rc, 0)
        self.assertGreater(spa.azimuth, 160.0,
                           msg=f"Azimut {spa.azimuth:.1f}° – Sonne sollte um solar noon südlich stehen")
        self.assertLess(spa.azimuth, 200.0,
                        msg=f"Azimut {spa.azimuth:.1f}° – Sonne sollte um solar noon südlich stehen")
        self.assertGreater(spa.e, 0.0,
                           msg="Sonne muss mittags über dem Horizont stehen")

    def test_midnight_sun_below_horizon_switzerland(self):
        """Um Mitternacht UTC ist die Sonne in der Schweiz unter dem Horizont."""
        rc, spa = _make_spa(2024, 6, 21, 0, 0, 0.0, 47.37, 8.54,
                            408, 1013.25, 15.0, 69)
        self.assertEqual(rc, 0)
        self.assertLess(spa.e, 0.0,
                        msg=f"Elevation {spa.e:.2f}° – Sonne soll um Mitternacht UTC "
                            "unter Horizont sein")


# ---------------------------------------------------------------------------

if __name__ == '__main__':
    unittest.main(verbosity=2)
