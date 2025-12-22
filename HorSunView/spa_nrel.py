# -*- coding: utf-8 -*-
"""spa_nrel.py

Compatibility wrapper around the strict NREL SPA port (spa_strict.py).

This keeps the previously-used plugin API:

    az_deg, el_deg = spa_calculate(dt_utc, lat, lon, elevation_m, ...)
    az_deg, el_deg, lst_hours = spa_calculate(..., return_lst=True)

Where:
- dt_utc is a datetime (naive interpreted as UTC, or timezone-aware).
- azimuth is degrees from North, clockwise (0..360).
- elevation is degrees above horizon.

Internally, it calls spa_strict.spa_calculate() with SPA_ZA and computes LST via the equation of time.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple, Union

from .spa_strict import (
    SpaData,
    spa_calculate as _spa_calculate_struct,
    SPA_ZA,
    sun_mean_longitude,
    eot as _eot_minutes,
)


def delta_t_estimate_seconds(year: int) -> float:
    """Rough ΔT estimate in seconds for years near the present.

    This replicates the previous lightweight approach. For exact replication against a reference run,
    pass delta_t explicitly to spa_calculate().
    """
    # Simple piecewise approximation around early 2000s; adjust as needed or override.
    # (Kept intentionally conservative; user workflows often pass ΔT explicitly.)
    y = float(year)
    if y < 2005:
        return 64.7
    if y < 2015:
        return 67.0
    if y < 2025:
        return 69.0
    return 71.0


def spa_calculate(
    dt_utc: datetime,
    lat: float,
    lon: float,
    elevation_m: float,
    pressure_mbar: float = 1013.25,
    temperature_c: float = 15.0,
    delta_t: float | None = None,
    delta_ut1: float = 0.0,
    atmos_refract_deg: float = 0.5667,
    return_lst: bool = False,
) -> Union[Tuple[float, float], Tuple[float, float, float]]:
    """Compute sun azimuth/elevation using NREL SPA (strict port).

    Parameters
    ----------
    dt_utc : datetime
        UTC timestamp. If naive, interpreted as UTC.
    lat, lon : float
        Degrees (WGS84): latitude [-90..90], longitude [-180..180].
    elevation_m : float
        Observer elevation above sea level [m].
    pressure_mbar : float
        Local atmospheric pressure [mbar].
    temperature_c : float
        Local temperature [°C].
    delta_t : float | None
        ΔT = TT - UT1 [s]. If None, a simple estimate is used.
    delta_ut1 : float
        UT1 - UTC [s]. If unknown, 0 is acceptable for most plotting use.
    atmos_refract_deg : float
        Atmospheric refraction at sunrise/sunset [deg]. Default matches NREL sample (0.5667°).
    return_lst : bool
        If True, also return local solar time (apparent) in hours [0..24).

    Returns
    -------
    (azimuth_deg, elevation_deg) or (azimuth_deg, elevation_deg, lst_hours)
    """
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    else:
        dt_utc = dt_utc.astimezone(timezone.utc)

    if delta_t is None:
        delta_t = delta_t_estimate_seconds(dt_utc.year)

    spa = SpaData(
        year=dt_utc.year,
        month=dt_utc.month,
        day=dt_utc.day,
        hour=dt_utc.hour,
        minute=dt_utc.minute,
        second=dt_utc.second + dt_utc.microsecond / 1e6,
        delta_ut1=float(delta_ut1),
        delta_t=float(delta_t),
        timezone=0.0,
        longitude=float(lon),
        latitude=float(lat),
        elevation=float(elevation_m),
        pressure=float(pressure_mbar),
        temperature=float(temperature_c),
        slope=0.0,
        azm_rotation=0.0,
        atmos_refract=float(atmos_refract_deg),
        function=SPA_ZA,
    )

    rc = _spa_calculate_struct(spa)
    if rc != 0:
        raise ValueError(f"SPA input validation failed with code {rc}")

    az = spa.azimuth
    el = spa.e

    if not return_lst:
        return az, el

    # Local solar time (apparent) in hours, using SPA equation of time definition.
    ut_hours = dt_utc.hour + dt_utc.minute / 60.0 + (dt_utc.second + dt_utc.microsecond / 1e6) / 3600.0
    m = sun_mean_longitude(spa.jme)
    eot_minutes = _eot_minutes(m, spa.alpha, spa.del_psi, spa.epsilon)
    lst = (ut_hours + eot_minutes / 60.0 + lon / 15.0) % 24.0

    return az, el, lst
