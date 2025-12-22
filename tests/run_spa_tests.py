# -*- coding: utf-8 -*-
"""
Minimal self-contained test runner for spa_strict.py.

Usage:
  python -m tests.run_spa_tests
or
  python tests/run_spa_tests.py

The numeric reference values are taken from the official NREL SPA distribution
(spa_tester.c comments) and the NREL technical report's appendix tables.

This runner intentionally uses plain asserts (no pytest dependency), so it can
run in QGIS plugin contexts or simple CI.
"""

from __future__ import annotations

import math

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from spa_strict import (
    SpaData,
    spa_calculate,
    julian_day,
    SPA_ALL,
)


def assert_close(name: str, got: float, exp: float, tol: float) -> None:
    if abs(got - exp) > tol:
        raise AssertionError(
            f"{name}: got {got!r}, expected {exp!r}, |diff|={abs(got-exp)} > {tol}"
        )


def test_julian_day_table_a41() -> None:
    # NREL report (Reda & Andreas 2008), Table A4.1 "Julian Day Example Calculations"
    cases = [
        # year, month, day, hour, minute, second, delta_ut1, tz, expected_jd
        (-4712, 1, 1, 12, 0, 0.0, 0.0, 0.0, 0.0),
        (2000, 1, 1, 12, 0, 0.0, 0.0, 0.0, 2451545.0),
        (1999, 1, 1, 0, 0, 0.0, 0.0, 0.0, 2451179.5),
        (1987, 1, 27, 0, 0, 0.0, 0.0, 0.0, 2446822.5),
        (1987, 6, 19, 12, 0, 0.0, 0.0, 0.0, 2446966.0),
        (1988, 1, 27, 0, 0, 0.0, 0.0, 0.0, 2447187.5),
        (1988, 6, 19, 12, 0, 0.0, 0.0, 0.0, 2447332.0),
        (1900, 1, 1, 0, 0, 0.0, 0.0, 0.0, 2415020.5),
        (1600, 1, 1, 0, 0, 0.0, 0.0, 0.0, 2305447.5),
        (1600, 12, 31, 0, 0, 0.0, 0.0, 0.0, 2305812.5),
        (837, 4, 10, 7, 12, 0.0, 0.0, 0.0, 2026871.8),
        (-1000, 7, 12, 12, 0, 0.0, 0.0, 0.0, 1356001.0),
        (-1000, 2, 29, 0, 0, 0.0, 0.0, 0.0, 1355866.5),
        (-1001, 8, 17, 21, 36, 0.0, 0.0, 0.0, 1355671.4),
        (-4712, 1, 1, 0, 0, 0.0, 0.0, 0.0, -0.5),
    ]
    for (y, mo, d, h, mi, s, dut1, tz, exp) in cases:
        got = julian_day(y, mo, d, h, mi, s, dut1, tz)
        # The table is rounded (1 decimal) for some rows.
        assert_close(f"JD({y}-{mo:02d}-{d:02d} {h:02d}:{mi:02d})", got, exp, tol=0.05)


def test_spa_example_table_a51() -> None:
    # Values from spa_tester.c (official NREL SPA distribution), matching Table A5.1.
    spa = SpaData(
        year=2003,
        month=10,
        day=17,
        hour=12,
        minute=30,
        second=30.0,
        delta_ut1=0.0,
        delta_t=67.0,
        timezone=-7.0,
        longitude=-105.1786,
        latitude=39.742476,
        elevation=1830.14,
        pressure=820.0,
        temperature=11.0,
        slope=30.0,
        azm_rotation=-10.0,
        atmos_refract=0.5667,
        function=SPA_ALL,
    )
    rc = spa_calculate(spa)
    assert rc == 0, f"spa_calculate returned {rc}"

    # Key intermediate values
    assert_close("jd", spa.jd, 2452930.312847, 1e-6)
    assert_close("L", spa.l, 24.0182616917, 1e-7)
    assert_close("B", spa.b, -0.0001011219, 1e-10)
    assert_close("R", spa.r, 0.9965422974, 1e-10)
    assert_close("H", spa.h, 11.105900, 5e-6)

    # Core outputs
    assert_close("zenith", spa.zenith, 50.111622, 5e-6)
    assert_close("azimuth", spa.azimuth, 194.340241, 5e-6)
    assert_close("incidence", spa.incidence, 25.187000, 5e-6)
    assert_close("eot", spa.eot, 14.641503, 1e-5)

    # RTS outputs: the official spa_tester.c prints HH:MM:SS using truncation.
    def hms_trunc(hours_float: float):
        h = int(hours_float)
        m_float = 60.0 * (hours_float - int(hours_float))
        m = int(m_float)
        s = int(60.0 * (m_float - int(m_float)))
        return h, m, s

    assert hms_trunc(spa.sunrise) == (6, 12, 43), f"sunrise HMS mismatch: {hms_trunc(spa.sunrise)}"
    assert hms_trunc(spa.sunset) == (17, 20, 19), f"sunset HMS mismatch: {hms_trunc(spa.sunset)}"


def main() -> int:
    test_julian_day_table_a41()
    test_spa_example_table_a51()
    print("All SPA strict tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
