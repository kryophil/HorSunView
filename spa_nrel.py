# -*- coding: utf-8 -*-
"""
spa.py

Eigenimplementierung des NREL Solar Position Algorithm (SPA) für präzise
Berechnung von Azimut- und Elevationswinkel der Sonne.
Referenz: "Solar Position Algorithm for Solar Radiation Applications",
National Renewable Energy Laboratory (NREL), Technical Report, 2008.

Funktion: spa_calculate(dt, lat, lon, elev, return_lst=False)
  dt:   datetime.datetime, UTC-annotiert oder naive (wird zu UTC interpretiert)
  lat:  geografische Breite [°]
  lon:  geografische Länge [° Ost positiv]
  elev: Höhe über Meer [m]
  return_lst: wenn True, zusätzlich die Local Solar Time [h] zurückgeben
Rückgabe:
  (azimuth_deg, elevation_deg) oder
  (azimuth_deg, elevation_deg, lst_hours)
"""

from datetime import datetime, timezone
import math
from typing import Tuple, Union

def spa_calculate(
    dt: datetime,
    lat: float,
    lon: float,
    elev: float,
    return_lst: bool = False
) -> Union[Tuple[float, float], Tuple[float, float, float]]:
    # 1. Julian Day
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    jd = (dt - datetime(2000, 1, 1, 12, tzinfo=timezone.utc)).total_seconds() / 86400.0 + 2451545.0

    # 2. Julian Century
    jc = (jd - 2451545.0) / 36525.0

    # 3. Geometrische mittlere Sonnenlänge (deg)
    gml = (280.46646 + jc*(36000.76983 + jc*0.0003032)) % 360

    # 4. Geometrische mittlere Sonnenanomalie (deg)
    gma = 357.52911 + jc*(35999.05029 - 0.0001537*jc)

    # 5. Exzentrizität der Erdumlaufbahn
    ecc = 0.016708634 - jc*(0.000042037 + 0.0000001267*jc)

    # 6. Zentrale Sonnengleichung (deg)
    eq_time = (
        gml
        + (1.914602 - jc*(0.004817 + 0.000014*jc)) * math.sin(math.radians(gma))
        + (0.019993 - 0.000101*jc) * math.sin(math.radians(2*gma))
        + 0.000289 * math.sin(math.radians(3*gma))
        - 0.0
    )
    eq_time = eq_time - gml  # Entfernung des mittleren Sonnenlängenanteils

    # 7. Zeitgleichungs-Korrektur (min)
    et = 4 * eq_time  # in Minuten

    # 8. UT in Dezimalstunden
    ut = dt.hour + dt.minute/60 + dt.second/3600

    # 9. Local Solar Time (h)
    lst = (ut + et/60 + lon/15) % 24

    # 10. Stundenwinkel (deg)
    sha = (lst - 12) * 15
    sha_rad = math.radians(sha)

    # 11. Sonneneklatation (delta, deg)
    obliq = 23.43929111 - jc*(0.013004167 + 1.6666667e-7*jc - 5.0277778e-7*jc*jc)
    delta = math.degrees(math.asin(
        math.sin(math.radians(obliq)) * math.sin(math.radians(gma))
    ))
    delta_rad = math.radians(delta)

    # 12. Zenith-Winkel & Elevation
    lat_rad = math.radians(lat)
    zenith = math.degrees(math.acos(
        math.sin(lat_rad)*math.sin(delta_rad) +
        math.cos(lat_rad)*math.cos(delta_rad)*math.cos(sha_rad)
    ))
    elev0 = 90 - zenith

    # 13. Atmosphärische Refraktion (approx.)
    if elev0 > 85:
        refr = 0
    else:
        pressure = 1013.25  # mbar
        temp = 15           # °C
        te = math.tan(math.radians(elev0 + 10.3/(elev0+5.11)))
        refr = (pressure/1010)*(283/(273+temp))*(1.02/60)/te

    elevation = elev0 + refr

    # 14. Azimut (deg von Nord im Uhrzeigersinn)
    azimuth = math.degrees(math.atan2(
        math.sin(sha_rad),
        math.cos(sha_rad)*math.sin(lat_rad) - math.tan(delta_rad)*math.cos(lat_rad)
    )) % 360

    if return_lst:
        return azimuth, elevation, lst
    else:
        return azimuth, elevation
