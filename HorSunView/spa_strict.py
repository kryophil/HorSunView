# -*- coding: utf-8 -*-
"""
spa_strict.py

Strict Python port of the NREL SPA (Solar Position Algorithm), based on the reference C implementation
published by NREL (Reda & Andreas, 2008) and distributed at midcdmz.nrel.gov.

Design goals:
- Parity with the original C version: same constants, same validation rules, same outputs.
- Usable from a QGIS plugin without external dependencies.

Public API:
- SpaData: dataclass mirroring the original `spa_data` struct
- spa_calculate(spa: SpaData) -> int : fills outputs, returns SPA error code (0 = OK)
- spa_calculate_utc(dt_utc, lat, lon, elevation_m, pressure_mbar, temperature_c, delta_t_s, ...) -> (azimuth_deg, elevation_deg)
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from datetime import datetime, timezone
from typing import Optional, Tuple


PI = 3.1415926535897932384626433832795028841971
SUN_RADIUS = 0.26667

SPA_ZA = 0
SPA_ZA_INC = 1
SPA_ZA_RTS = 2
SPA_ALL = 3

SUN_RISE = 0
SUN_TRANSIT = 1
SUN_SET = 2

TERM_A = 0
TERM_B = 1
TERM_C = 2

TERM_X0 = 0
TERM_X1 = 1
TERM_X2 = 2
TERM_X3 = 3
TERM_X4 = 4
TERM_Y_COUNT = 5
TERM_X_COUNT = 5

TERM_PSI_A = 0
TERM_PSI_B = 1
TERM_EPS_C = 2
TERM_EPS_D = 3

JD_MINUS = 0
JD_ZERO = 1
JD_PLUS = 2

# Periodic terms (verbatim from spa.c)
l_subcount = [64,34,20,7,3,1]
b_subcount = [5,2]
r_subcount = [40,10,6,2,1]

L_TERMS = [
    [
        [175347046.0,0,0],
        [3341656.0,4.6692568,6283.07585],
        [34894.0,4.6261,12566.1517],
        [3497.0,2.7441,5753.3849],
        [3418.0,2.8289,3.5231],
        [3136.0,3.6277,77713.7715],
        [2676.0,4.4181,7860.4194],
        [2343.0,6.1352,3930.2097],
        [1324.0,0.7425,11506.7698],
        [1273.0,2.0371,529.691],
        [1199.0,1.1096,1577.3435],
        [990,5.233,5884.927],
        [902,2.045,26.298],
        [857,3.508,398.149],
        [780,1.179,5223.694],
        [753,2.533,5507.553],
        [505,4.583,18849.228],
        [492,4.205,775.523],
        [357,2.92,0.067],
        [317,5.849,11790.629],
        [284,1.899,796.298],
        [271,0.315,10977.079],
        [243,0.345,5486.778],
        [206,4.806,2544.314],
        [205,1.869,5573.143],
        [202,2.458,6069.777],
        [156,0.833,213.299],
        [132,3.411,2942.463],
        [126,1.083,20.775],
        [115,0.645,0.98],
        [103,0.636,4694.003],
        [102,0.976,15720.839],
        [102,4.267,7.114],
        [99,6.21,2146.17],
        [98,0.68,155.42],
        [86,5.98,161000.69],
        [85,1.3,6275.96],
        [85,3.67,71430.7],
        [80,1.81,17260.15],
        [79,3.04,12036.46],
        [75,1.76,5088.63],
        [74,3.5,3154.69],
        [74,4.68,801.82],
        [70,0.83,9437.76],
        [62,3.98,8827.39],
        [61,1.82,7084.9],
        [57,2.78,6286.6],
        [56,4.39,14143.5],
        [56,3.47,6279.55],
        [52,0.19,12139.55],
        [52,1.33,1748.02],
        [51,0.28,5856.48],
        [49,0.49,1194.45],
        [41,5.37,8429.24],
        [41,2.4,19651.05],
        [39,6.17,10447.39],
        [37,6.04,10213.29],
        [37,2.57,1059.38],
        [36,1.71,2352.87],
        [36,1.78,6812.77],
        [33,0.59,17789.85],
        [30,0.44,83996.85],
        [30,2.74,1349.87],
        [25,3.16,4690.48]
    ],
    [
        [628331966747.0,0,0],
        [206059.0,2.678235,6283.07585],
        [4303.0,2.6351,12566.1517],
        [425.0,1.59,3.523],
        [119.0,5.796,26.298],
        [109.0,2.966,1577.344],
        [93,2.59,18849.23],
        [72,1.14,529.69],
        [68,1.87,398.15],
        [67,4.41,5507.55],
        [59,2.89,5223.69],
        [56,2.17,155.42],
        [45,0.4,796.3],
        [36,0.47,775.52],
        [29,2.65,7.11],
        [21,5.34,0.98],
        [19,1.85,5486.78],
        [19,4.97,213.3],
        [17,2.99,6275.96],
        [16,0.03,2544.31],
        [16,1.43,2146.17],
        [15,1.21,10977.08],
        [12,2.83,1748.02],
        [12,3.26,5088.63],
        [12,5.27,1194.45],
        [12,2.08,4694],
        [11,0.77,553.57],
        [10,1.3,6286.6],
        [10,4.24,1349.87],
        [9,2.7,242.73],
        [9,5.64,951.72],
        [8,5.3,2352.87],
        [6,2.65,9437.76],
        [6,4.67,4690.48]
    ],
    [
        [52919.0,0,0],
        [8720.0,1.0721,6283.0758],
        [309.0,0.867,12566.152],
        [27,0.05,3.52],
        [16,5.19,26.3],
        [16,3.68,155.42],
        [10,0.76,18849.23],
        [9,2.06,77713.77],
        [7,0.83,775.52],
        [5,4.66,1577.34],
        [4,1.03,7.11],
        [4,3.44,5573.14],
        [3,5.14,796.3],
        [3,6.05,5507.55],
        [3,1.19,242.73],
        [3,6.12,529.69],
        [3,0.31,398.15],
        [3,2.28,553.57],
        [2,4.38,5223.69],
        [2,3.75,0.98]
    ],
    [
        [289.0,5.844,6283.076],
        [35,0,0],
        [17,5.49,12566.15],
        [3,5.2,155.42],
        [1,4.72,3.52],
        [1,5.3,18849.23],
        [1,5.97,242.73]
    ],
    [
        [114.0,3.142,0],
        [8,4.13,6283.08],
        [1,3.84,12566.15]
    ],
    [
        [1,3.14,0]
    ]
]

B_TERMS = [
    [
        [280.0,3.199,84334.662],
        [102.0,5.422,5507.553],
        [80,3.88,5223.69],
        [44,3.7,2352.87],
        [32,4,1577.34]
    ],
    [
        [9,3.9,5507.55],
        [6,1.73,5223.69]
    ]
]

R_TERMS = [
    [
        [100013989.0,0,0],
        [1670700.0,3.0984635,6283.07585],
        [13956.0,3.05525,12566.1517],
        [3084.0,5.1985,77713.7715],
        [1628.0,1.1739,5753.3849],
        [1576.0,2.8469,7860.4194],
        [925.0,5.453,11506.77],
        [542.0,4.564,3930.21],
        [472.0,3.661,5884.927],
        [346.0,0.964,5507.553],
        [329.0,5.9,5223.694],
        [307.0,0.299,5573.143],
        [243.0,4.273,11790.629],
        [212.0,5.847,1577.344],
        [186.0,5.022,10977.079],
        [175.0,3.012,18849.228],
        [110.0,5.055,5486.778],
        [98,0.89,6069.78],
        [86,5.69,15720.84],
        [86,1.27,161000.69],
        [65,0.27,17260.15],
        [63,0.92,529.69],
        [57,2.01,83996.85],
        [56,5.24,71430.7],
        [49,3.25,2544.31],
        [47,2.58,775.52],
        [45,5.54,9437.76],
        [43,6.01,6275.96],
        [39,5.36,4694],
        [38,2.39,8827.39],
        [37,0.83,19651.05],
        [37,4.9,12139.55],
        [36,1.67,12036.46],
        [35,1.84,2942.46],
        [33,0.24,7084.9],
        [32,0.18,5088.63],
        [32,1.78,398.15],
        [28,1.21,6286.6],
        [28,1.9,6279.55],
        [26,4.59,10447.39]
    ],
    [
        [103019.0,1.10749,6283.07585],
        [1721.0,1.0644,12566.1517],
        [702.0,3.142,0],
        [32,1.02,18849.23],
        [31,2.84,5507.55],
        [25,1.32,5223.69],
        [18,1.42,1577.34],
        [10,5.91,10977.08],
        [9,1.42,6275.96],
        [9,0.27,5486.78]
    ],
    [
        [4359.0,5.7846,6283.0758],
        [124.0,5.579,12566.152],
        [12,3.14,0],
        [9,3.63,77713.77],
        [6,1.87,5573.14],
        [3,5.47,18849.23]
    ],
    [
        [145.0,4.273,6283.076],
        [7,3.92,12566.15]
    ],
    [
        [4,2.56,6283.08]
    ]
]

Y_TERMS = [
    [0,0,0,0,1],
    [-2,0,0,2,2],
    [0,0,0,2,2],
    [0,0,0,0,2],
    [0,1,0,0,0],
    [0,0,1,0,0],
    [-2,1,0,2,2],
    [0,0,0,2,1],
    [0,0,1,2,2],
    [-2,-1,0,2,2],
    [-2,0,1,0,0],
    [-2,0,0,2,1],
    [0,0,-1,2,2],
    [2,0,0,0,0],
    [0,0,1,0,1],
    [2,0,-1,2,2],
    [0,0,-1,0,1],
    [0,0,1,2,1],
    [-2,0,2,0,0],
    [0,0,-2,2,1],
    [2,0,0,2,2],
    [0,0,2,2,2],
    [0,0,2,0,0],
    [-2,0,1,2,2],
    [0,0,0,2,0],
    [-2,0,0,2,0],
    [0,0,-1,2,1],
    [0,2,0,0,0],
    [2,0,-1,0,1],
    [-2,2,0,2,2],
    [0,1,0,0,1],
    [-2,0,1,0,1],
    [0,-1,0,0,1],
    [0,0,2,-2,0],
    [2,0,-1,2,1],
    [2,0,1,2,2],
    [0,1,0,2,2],
    [-2,1,1,0,0],
    [0,-1,0,2,2],
    [2,0,0,2,1],
    [2,0,1,0,0],
    [-2,0,2,2,2],
    [-2,0,1,2,1],
    [2,0,-2,0,1],
    [2,0,0,0,1],
    [0,-1,1,0,0],
    [-2,-1,0,2,1],
    [-2,0,0,0,1],
    [0,0,2,2,1],
    [-2,0,2,0,1],
    [-2,1,0,2,1],
    [0,0,1,-2,0],
    [-1,0,1,0,0],
    [-2,1,0,0,0],
    [1,0,0,0,0],
    [0,0,1,2,0],
    [0,0,-2,2,2],
    [-1,-1,1,0,0],
    [0,1,1,0,0],
    [0,-1,1,2,2],
    [2,-1,-1,2,2],
    [0,0,3,2,2],
    [2,-1,0,2,2],
]

PE_TERMS = [
    [-171996,-174.2,92025,8.9],
    [-13187,-1.6,5736,-3.1],
    [-2274,-0.2,977,-0.5],
    [2062,0.2,-895,0.5],
    [1426,-3.4,54,-0.1],
    [712,0.1,-7,0],
    [-517,1.2,224,-0.6],
    [-386,-0.4,200,0],
    [-301,0,129,-0.1],
    [217,-0.5,-95,0.3],
    [-158,0,0,0],
    [129,0.1,-70,0],
    [123,0,-53,0],
    [63,0,0,0],
    [63,0.1,-33,0],
    [-59,0,26,0],
    [-58,-0.1,32,0],
    [-51,0,27,0],
    [48,0,0,0],
    [46,0,-24,0],
    [-38,0,16,0],
    [-31,0,13,0],
    [29,0,0,0],
    [29,0,-12,0],
    [26,0,0,0],
    [-22,0,0,0],
    [21,0,-10,0],
    [17,-0.1,0,0],
    [16,0,-8,0],
    [-16,0.1,7,0],
    [-15,0,9,0],
    [-13,0,7,0],
    [-12,0,6,0],
    [11,0,0,0],
    [-10,0,5,0],
    [-8,0,3,0],
    [7,0,-3,0],
    [-7,0,0,0],
    [-7,0,3,0],
    [-7,0,3,0],
    [6,0,0,0],
    [6,0,-3,0],
    [6,0,-3,0],
    [-6,0,3,0],
    [-6,0,3,0],
    [5,0,0,0],
    [-5,0,3,0],
    [-5,0,3,0],
    [-5,0,3,0],
    [4,0,0,0],
    [4,0,0,0],
    [4,0,0,0],
    [-4,0,0,0],
    [-4,0,0,0],
    [-4,0,0,0],
    [3,0,0,0],
    [-3,0,0,0],
    [-3,0,0,0],
    [-3,0,0,0],
    [-3,0,0,0],
    [-3,0,0,0],
    [-3,0,0,0],
    [-3,0,0,0],
]


L_COUNT = 6
B_COUNT = 2
R_COUNT = 5
Y_COUNT = 63
JD_COUNT = 3
SUN_COUNT = 3

@dataclass
class SpaData:
    # INPUT
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: float
    delta_ut1: float
    delta_t: float
    timezone: float
    longitude: float
    latitude: float
    elevation: float
    pressure: float
    temperature: float
    slope: float
    azm_rotation: float
    atmos_refract: float
    function: int = SPA_ZA

    # OUTPUT (filled by spa_calculate)
    jd: float = 0.0
    jc: float = 0.0
    jde: float = 0.0
    jce: float = 0.0
    jme: float = 0.0
    l: float = 0.0
    b: float = 0.0
    r: float = 0.0
    theta: float = 0.0
    beta: float = 0.0
    x0: float = 0.0
    x1: float = 0.0
    x2: float = 0.0
    x3: float = 0.0
    x4: float = 0.0
    del_psi: float = 0.0
    del_epsilon: float = 0.0
    epsilon0: float = 0.0
    epsilon: float = 0.0
    del_tau: float = 0.0
    lamda: float = 0.0
    nu0: float = 0.0
    nu: float = 0.0
    alpha: float = 0.0
    delta: float = 0.0
    h: float = 0.0
    xi: float = 0.0
    del_alpha: float = 0.0
    delta_prime: float = 0.0
    alpha_prime: float = 0.0
    h_prime: float = 0.0
    e0: float = 0.0
    del_e: float = 0.0
    e: float = 0.0
    zenith: float = 0.0
    azimuth_astro: float = 0.0
    azimuth: float = 0.0
    incidence: float = 0.0

    # EOT & RTS outputs
    m: float = 0.0
    eot: float = 0.0
    srha: float = 0.0
    ssha: float = 0.0
    sta: float = 0.0
    suntransit: float = 0.0
    sunrise: float = 0.0
    sunset: float = 0.0

# -----------------------------
# Helpers (verbatim semantics from spa.c)
# -----------------------------

def rad2deg(radians: float) -> float:
    return (180.0 / PI) * radians

def deg2rad(degrees: float) -> float:
    return (PI / 180.0) * degrees

def integer(value: float) -> int:
    # C: implicit cast to int (trunc toward zero)
    return int(value)

def limit_degrees(degrees: float) -> float:
    degrees /= 360.0
    limited = 360.0 * (degrees - math.floor(degrees))
    if limited < 0:
        limited += 360.0
    return limited

def limit_degrees180pm(degrees: float) -> float:
    degrees /= 360.0
    limited = 360.0 * (degrees - math.floor(degrees))
    if limited < -180.0:
        limited += 360.0
    elif limited > 180.0:
        limited -= 360.0
    return limited

def limit_degrees180(degrees: float) -> float:
    degrees /= 180.0
    limited = 180.0 * (degrees - math.floor(degrees))
    if limited < 0:
        limited += 180.0
    return limited

def limit_zero2one(value: float) -> float:
    limited = value - math.floor(value)
    if limited < 0:
        limited += 1.0
    return limited

def limit_minutes(minutes: float) -> float:
    limited = minutes
    if limited < -20.0:
        limited += 1440.0
    elif limited > 20.0:
        limited -= 1440.0
    return limited

def dayfrac_to_local_hr(dayfrac: float, timezone: float) -> float:
    return 24.0 * limit_zero2one(dayfrac + timezone / 24.0)

def third_order_polynomial(a: float, b: float, c: float, d: float, x: float) -> float:
    return ((a * x + b) * x + c) * x + d

def validate_inputs(spa: SpaData) -> int:
    if (spa.year < -2000) or (spa.year > 6000): return 1
    if (spa.month < 1) or (spa.month > 12): return 2
    if (spa.day < 1) or (spa.day > 31): return 3
    if (spa.hour < 0) or (spa.hour > 24): return 4
    if (spa.minute < 0) or (spa.minute > 59): return 5
    if (spa.second < 0) or (spa.second >= 60): return 6
    if (spa.pressure < 0) or (spa.pressure > 5000): return 12
    if (spa.temperature <= -273) or (spa.temperature > 6000): return 13
    if (spa.delta_ut1 <= -1) or (spa.delta_ut1 >= 1): return 17
    if (spa.hour == 24) and (spa.minute > 0): return 5
    if (spa.hour == 24) and (spa.second > 0): return 6

    if abs(spa.delta_t) > 8000: return 7
    if abs(spa.timezone) > 18: return 8
    if abs(spa.longitude) > 180: return 9
    if abs(spa.latitude) > 90: return 10
    if abs(spa.elevation) > 6500000: return 11
    if abs(spa.slope) > 360: return 14
    if abs(spa.azm_rotation) > 360: return 15
    if abs(spa.atmos_refract) > 5: return 16

    return 0

def julian_day(year: int, month: int, day: int, hour: int, minute: int, second: float,
               delta_ut1: float, timezone: float) -> float:
    day_decimal = day + (hour - timezone + (minute + (second + delta_ut1) / 60.0) / 60.0) / 24.0

    if month < 3:
        month += 12
        year -= 1

    jd = integer(365.25 * (year + 4716.0)) + integer(30.6001 * (month + 1)) + day_decimal - 1524.5

    if jd > 2299160.0:
        a = integer(year / 100.0)
        jd += 2 - a + integer(a / 4.0)

    return jd

def julian_century(jd: float) -> float:
    return (jd - 2451545.0) / 36525.0

def julian_ephemeris_day(jd: float, delta_t: float) -> float:
    return jd + delta_t / 86400.0

def julian_ephemeris_century(jde: float) -> float:
    return (jde - 2451545.0) / 36525.0

def julian_ephemeris_millennium(jce: float) -> float:
    return jce / 10.0

def earth_periodic_term_summation(terms, count: int, jme: float) -> float:
    s = 0.0
    for i in range(count):
        s += terms[i][TERM_A] * math.cos(terms[i][TERM_B] + terms[i][TERM_C] * jme)
    return s

def earth_values(term_sum, count: int, jme: float) -> float:
    s = 0.0
    for i in range(count):
        s += term_sum[i] * (jme ** i)
    s /= 1.0e8
    return s

def earth_heliocentric_longitude(jme: float) -> float:
    sums = [0.0] * L_COUNT
    for i in range(L_COUNT):
        sums[i] = earth_periodic_term_summation(L_TERMS[i], l_subcount[i], jme)
    return limit_degrees(rad2deg(earth_values(sums, L_COUNT, jme)))

def earth_heliocentric_latitude(jme: float) -> float:
    sums = [0.0] * B_COUNT
    for i in range(B_COUNT):
        sums[i] = earth_periodic_term_summation(B_TERMS[i], b_subcount[i], jme)
    return rad2deg(earth_values(sums, B_COUNT, jme))

def earth_radius_vector(jme: float) -> float:
    sums = [0.0] * R_COUNT
    for i in range(R_COUNT):
        sums[i] = earth_periodic_term_summation(R_TERMS[i], r_subcount[i], jme)
    return earth_values(sums, R_COUNT, jme)

def geocentric_longitude(l: float) -> float:
    theta = l + 180.0
    if theta >= 360.0:
        theta -= 360.0
    return theta

def geocentric_latitude(b: float) -> float:
    return -b

def mean_elongation_moon_sun(jce: float) -> float:
    return third_order_polynomial(1.0/189474.0, -0.0019142, 445267.11148, 297.85036, jce)

def mean_anomaly_sun(jce: float) -> float:
    return third_order_polynomial(-1.0/300000.0, -0.0001603, 35999.05034, 357.52772, jce)

def mean_anomaly_moon(jce: float) -> float:
    return third_order_polynomial(1.0/56250.0, 0.0086972, 477198.867398, 134.96298, jce)

def argument_latitude_moon(jce: float) -> float:
    return third_order_polynomial(1.0/327270.0, -0.0036825, 483202.017538, 93.27191, jce)

def ascending_longitude_moon(jce: float) -> float:
    return third_order_polynomial(1.0/450000.0, 0.0020708, -1934.136261, 125.04452, jce)

def xy_term_summation(i: int, x) -> float:
    s = 0.0
    for j in range(TERM_Y_COUNT):
        s += x[j] * Y_TERMS[i][j]
    return s

def nutation_longitude_and_obliquity(jce: float, x) -> Tuple[float, float]:
    sum_psi = 0.0
    sum_eps = 0.0
    for i in range(Y_COUNT):
        xy = deg2rad(xy_term_summation(i, x))
        sum_psi += (PE_TERMS[i][TERM_PSI_A] + jce * PE_TERMS[i][TERM_PSI_B]) * math.sin(xy)
        sum_eps += (PE_TERMS[i][TERM_EPS_C] + jce * PE_TERMS[i][TERM_EPS_D]) * math.cos(xy)
    del_psi = sum_psi / 36000000.0
    del_eps = sum_eps / 36000000.0
    return del_psi, del_eps

def ecliptic_mean_obliquity(jme: float) -> float:
    u = jme / 10.0
    return 84381.448 + u*(-4680.93 + u*(-1.55 + u*(1999.25 + u*(-51.38 + u*(-249.67 +
                       u*(  -39.05 + u*( 7.12 + u*(  27.87 + u*(  5.79 + u*2.45)))))))))

def ecliptic_true_obliquity(delta_epsilon: float, epsilon0: float) -> float:
    return delta_epsilon + epsilon0 / 3600.0

def aberration_correction(r: float) -> float:
    return -20.4898 / (3600.0 * r)

def apparent_sun_longitude(theta: float, delta_psi: float, delta_tau: float) -> float:
    return theta + delta_psi + delta_tau

def greenwich_mean_sidereal_time(jd: float, jc: float) -> float:
    return limit_degrees(280.46061837 + 360.98564736629 * (jd - 2451545.0) +
                         jc*jc*(0.000387933 - jc/38710000.0))

def greenwich_sidereal_time(nu0: float, delta_psi: float, epsilon: float) -> float:
    return nu0 + delta_psi * math.cos(deg2rad(epsilon))

def geocentric_right_ascension(lamda: float, epsilon: float, beta: float) -> float:
    lamda_rad = deg2rad(lamda)
    eps_rad = deg2rad(epsilon)
    return limit_degrees(rad2deg(math.atan2(
        math.sin(lamda_rad) * math.cos(eps_rad) - math.tan(deg2rad(beta)) * math.sin(eps_rad),
        math.cos(lamda_rad)
    )))

def geocentric_declination(beta: float, epsilon: float, lamda: float) -> float:
    beta_rad = deg2rad(beta)
    eps_rad = deg2rad(epsilon)
    return rad2deg(math.asin(
        math.sin(beta_rad) * math.cos(eps_rad) +
        math.cos(beta_rad) * math.sin(eps_rad) * math.sin(deg2rad(lamda))
    ))

def observer_hour_angle(nu: float, longitude: float, alpha_deg: float) -> float:
    return limit_degrees(nu + longitude - alpha_deg)

def sun_equatorial_horizontal_parallax(r: float) -> float:
    return 8.794 / (3600.0 * r)

def right_ascension_parallax_and_topocentric_dec(latitude: float, elevation: float,
                                                 xi: float, h: float, delta: float) -> Tuple[float, float]:
    lat_rad = deg2rad(latitude)
    xi_rad = deg2rad(xi)
    h_rad = deg2rad(h)
    delta_rad = deg2rad(delta)
    u = math.atan(0.99664719 * math.tan(lat_rad))
    y = 0.99664719 * math.sin(u) + elevation * math.sin(lat_rad) / 6378140.0
    x = math.cos(u) + elevation * math.cos(lat_rad) / 6378140.0

    delta_alpha_rad = math.atan2(-x * math.sin(xi_rad) * math.sin(h_rad),
                                 math.cos(delta_rad) - x * math.sin(xi_rad) * math.cos(h_rad))

    delta_prime = rad2deg(math.atan2((math.sin(delta_rad) - y * math.sin(xi_rad)) * math.cos(delta_alpha_rad),
                                     math.cos(delta_rad) - x * math.sin(xi_rad) * math.cos(h_rad)))

    delta_alpha = rad2deg(delta_alpha_rad)
    return delta_alpha, delta_prime

def topocentric_right_ascension(alpha_deg: float, delta_alpha: float) -> float:
    return alpha_deg + delta_alpha

def topocentric_local_hour_angle(h: float, delta_alpha: float) -> float:
    return h - delta_alpha

def topocentric_elevation_angle(latitude: float, delta_prime: float, h_prime: float) -> float:
    lat_rad = deg2rad(latitude)
    dp_rad = deg2rad(delta_prime)
    return rad2deg(math.asin(
        math.sin(lat_rad) * math.sin(dp_rad) +
        math.cos(lat_rad) * math.cos(dp_rad) * math.cos(deg2rad(h_prime))
    ))

def atmospheric_refraction_correction(pressure: float, temperature: float,
                                      atmos_refract: float, e0: float) -> float:
    del_e = 0.0
    if e0 >= -1 * (SUN_RADIUS + atmos_refract):
        del_e = (pressure / 1010.0) * (283.0 / (273.0 + temperature)) * 1.02 / (
            60.0 * math.tan(deg2rad(e0 + 10.3 / (e0 + 5.11)))
        )
    return del_e

def topocentric_elevation_angle_corrected(e0: float, delta_e: float) -> float:
    return e0 + delta_e

def topocentric_zenith_angle(e: float) -> float:
    return 90.0 - e

def topocentric_azimuth_angle_astro(h_prime: float, latitude: float, delta_prime: float) -> float:
    h_prime_rad = deg2rad(h_prime)
    lat_rad = deg2rad(latitude)
    return limit_degrees(rad2deg(math.atan2(
        math.sin(h_prime_rad),
        math.cos(h_prime_rad) * math.sin(lat_rad) - math.tan(deg2rad(delta_prime)) * math.cos(lat_rad)
    )))

def topocentric_azimuth_angle(azimuth_astro: float) -> float:
    return limit_degrees(azimuth_astro + 180.0)

def surface_incidence_angle(zenith: float, azimuth_astro: float, azm_rotation: float, slope: float) -> float:
    zenith_rad = deg2rad(zenith)
    slope_rad = deg2rad(slope)
    return rad2deg(math.acos(
        math.cos(zenith_rad) * math.cos(slope_rad) +
        math.sin(slope_rad) * math.sin(zenith_rad) * math.cos(deg2rad(azimuth_astro - azm_rotation))
    ))

def sun_mean_longitude(jme: float) -> float:
    return limit_degrees(280.4664567 + jme*(360007.6982779 + jme*(0.03032028 +
        jme*(1/49931.0 + jme*(-1/15300.0 + jme*(-1/2000000.0))))))

def eot(m: float, alpha: float, del_psi: float, epsilon: float) -> float:
    return limit_minutes(4.0*(m - 0.0057183 - alpha + del_psi * math.cos(deg2rad(epsilon))))

def approx_sun_transit_time(alpha_zero: float, longitude: float, nu: float) -> float:
    return (alpha_zero - longitude - nu) / 360.0

def sun_hour_angle_at_rise_set(latitude: float, delta_zero: float, h0_prime: float) -> float:
    h0 = -99999.0
    latitude_rad = deg2rad(latitude)
    delta_zero_rad = deg2rad(delta_zero)
    argument = (math.sin(deg2rad(h0_prime)) - math.sin(latitude_rad) * math.sin(delta_zero_rad)) / (
        math.cos(latitude_rad) * math.cos(delta_zero_rad)
    )
    if abs(argument) <= 1.0:
        h0 = limit_degrees180(rad2deg(math.acos(argument)))
    return h0

def approx_sun_rise_and_set(m_rts, h0: float) -> None:
    h0_dfrac = h0 / 360.0
    m_rts[SUN_RISE] = limit_zero2one(m_rts[SUN_TRANSIT] - h0_dfrac)
    m_rts[SUN_SET] = limit_zero2one(m_rts[SUN_TRANSIT] + h0_dfrac)
    m_rts[SUN_TRANSIT] = limit_zero2one(m_rts[SUN_TRANSIT])

def rts_alpha_delta_prime(ad, n: float) -> float:
    a = ad[JD_ZERO] - ad[JD_MINUS]
    b = ad[JD_PLUS] - ad[JD_ZERO]
    if abs(a) >= 2.0:
        a = limit_zero2one(a)
    if abs(b) >= 2.0:
        b = limit_zero2one(b)
    return ad[JD_ZERO] + n * (a + b + (b - a) * n) / 2.0

def rts_sun_altitude(latitude: float, delta_prime: float, h_prime: float) -> float:
    latitude_rad = deg2rad(latitude)
    delta_prime_rad = deg2rad(delta_prime)
    return rad2deg(math.asin(
        math.sin(latitude_rad) * math.sin(delta_prime_rad) +
        math.cos(latitude_rad) * math.cos(delta_prime_rad) * math.cos(deg2rad(h_prime))
    ))

def sun_rise_and_set(m_rts, h_rts, delta_prime, latitude: float, h_prime, h0_prime: float, sun: int) -> float:
    return m_rts[sun] + (h_rts[sun] - h0_prime) / (
        360.0 * math.cos(deg2rad(delta_prime[sun])) * math.cos(deg2rad(latitude)) * math.sin(deg2rad(h_prime[sun]))
    )

def calculate_geocentric_sun_right_ascension_and_declination(spa: SpaData) -> None:
    x = [0.0] * TERM_X_COUNT
    spa.jc = julian_century(spa.jd)
    spa.jde = julian_ephemeris_day(spa.jd, spa.delta_t)
    spa.jce = julian_ephemeris_century(spa.jde)
    spa.jme = julian_ephemeris_millennium(spa.jce)

    spa.l = earth_heliocentric_longitude(spa.jme)
    spa.b = earth_heliocentric_latitude(spa.jme)
    spa.r = earth_radius_vector(spa.jme)

    spa.theta = geocentric_longitude(spa.l)
    spa.beta = geocentric_latitude(spa.b)

    x[TERM_X0] = spa.x0 = mean_elongation_moon_sun(spa.jce)
    x[TERM_X1] = spa.x1 = mean_anomaly_sun(spa.jce)
    x[TERM_X2] = spa.x2 = mean_anomaly_moon(spa.jce)
    x[TERM_X3] = spa.x3 = argument_latitude_moon(spa.jce)
    x[TERM_X4] = spa.x4 = ascending_longitude_moon(spa.jce)

    spa.del_psi, spa.del_epsilon = nutation_longitude_and_obliquity(spa.jce, x)

    spa.epsilon0 = ecliptic_mean_obliquity(spa.jme)
    spa.epsilon = ecliptic_true_obliquity(spa.del_epsilon, spa.epsilon0)

    spa.del_tau = aberration_correction(spa.r)
    spa.lamda = apparent_sun_longitude(spa.theta, spa.del_psi, spa.del_tau)

    spa.nu0 = greenwich_mean_sidereal_time(spa.jd, spa.jc)
    spa.nu = greenwich_sidereal_time(spa.nu0, spa.del_psi, spa.epsilon)

    spa.alpha = geocentric_right_ascension(spa.lamda, spa.epsilon, spa.beta)
    spa.delta = geocentric_declination(spa.beta, spa.epsilon, spa.lamda)

def calculate_eot_and_sun_rise_transit_set(spa: SpaData) -> None:
    # Port of spa.c calculate_eot_and_sun_rise_transit_set()
    sun_rts = SpaData(**{k: getattr(spa, k) for k in SpaData.__dataclass_fields__ if k in (
        "year","month","day","hour","minute","second","delta_ut1","delta_t","timezone","longitude","latitude",
        "elevation","pressure","temperature","slope","azm_rotation","atmos_refract","function"
    )})
    # Copy outputs not needed; struct copy in C is full, but only inputs accessed here.
    m = sun_mean_longitude(spa.jme)
    spa.eot = eot(m, spa.alpha, spa.del_psi, spa.epsilon)

    sun_rts.hour = 0
    sun_rts.minute = 0
    sun_rts.second = 0.0
    sun_rts.delta_ut1 = 0.0
    sun_rts.timezone = 0.0

    sun_rts.jd = julian_day(sun_rts.year, sun_rts.month, sun_rts.day, sun_rts.hour,
                            sun_rts.minute, sun_rts.second, sun_rts.delta_ut1, sun_rts.timezone)

    calculate_geocentric_sun_right_ascension_and_declination(sun_rts)
    nu = sun_rts.nu

    sun_rts.delta_t = 0.0
    sun_rts.jd -= 1.0

    alpha = [0.0]*JD_COUNT
    delta = [0.0]*JD_COUNT
    for i in range(JD_COUNT):
        calculate_geocentric_sun_right_ascension_and_declination(sun_rts)
        alpha[i] = sun_rts.alpha
        delta[i] = sun_rts.delta
        sun_rts.jd += 1.0

    m_rts = [0.0]*SUN_COUNT
    nu_rts = [0.0]*SUN_COUNT
    h_rts = [0.0]*SUN_COUNT
    alpha_prime = [0.0]*SUN_COUNT
    delta_prime = [0.0]*SUN_COUNT
    h_prime = [0.0]*SUN_COUNT

    h0_prime = -1 * (SUN_RADIUS + spa.atmos_refract)

    m_rts[SUN_TRANSIT] = approx_sun_transit_time(alpha[JD_ZERO], spa.longitude, nu)
    h0 = sun_hour_angle_at_rise_set(spa.latitude, delta[JD_ZERO], h0_prime)

    if h0 >= 0:
        approx_sun_rise_and_set(m_rts, h0)

        for i in range(SUN_COUNT):
            nu_rts[i] = nu + 360.985647 * m_rts[i]
            n = m_rts[i] + spa.delta_t / 86400.0
            alpha_prime[i] = rts_alpha_delta_prime(alpha, n)
            delta_prime[i] = rts_alpha_delta_prime(delta, n)
            h_prime[i] = limit_degrees180pm(nu_rts[i] + spa.longitude - alpha_prime[i])
            h_rts[i] = rts_sun_altitude(spa.latitude, delta_prime[i], h_prime[i])

        spa.srha = h_prime[SUN_RISE]
        spa.ssha = h_prime[SUN_SET]
        spa.sta = h_rts[SUN_TRANSIT]

        spa.suntransit = dayfrac_to_local_hr(m_rts[SUN_TRANSIT] - h_prime[SUN_TRANSIT]/360.0, spa.timezone)

        spa.sunrise = dayfrac_to_local_hr(
            sun_rise_and_set(m_rts, h_rts, delta_prime, spa.latitude, h_prime, h0_prime, SUN_RISE),
            spa.timezone
        )
        spa.sunset = dayfrac_to_local_hr(
            sun_rise_and_set(m_rts, h_rts, delta_prime, spa.latitude, h_prime, h0_prime, SUN_SET),
            spa.timezone
        )
    else:
        spa.srha = spa.ssha = spa.sta = spa.suntransit = spa.sunrise = spa.sunset = -99999.0

def spa_calculate(spa: SpaData) -> int:
    result = validate_inputs(spa)
    if result != 0:
        return result

    spa.jd = julian_day(spa.year, spa.month, spa.day, spa.hour, spa.minute, spa.second, spa.delta_ut1, spa.timezone)

    calculate_geocentric_sun_right_ascension_and_declination(spa)

    spa.h = observer_hour_angle(spa.nu, spa.longitude, spa.alpha)
    spa.xi = sun_equatorial_horizontal_parallax(spa.r)

    spa.del_alpha, spa.delta_prime = right_ascension_parallax_and_topocentric_dec(
        spa.latitude, spa.elevation, spa.xi, spa.h, spa.delta
    )

    spa.alpha_prime = topocentric_right_ascension(spa.alpha, spa.del_alpha)
    spa.h_prime = topocentric_local_hour_angle(spa.h, spa.del_alpha)

    spa.e0 = topocentric_elevation_angle(spa.latitude, spa.delta_prime, spa.h_prime)
    spa.del_e = atmospheric_refraction_correction(spa.pressure, spa.temperature, spa.atmos_refract, spa.e0)
    spa.e = topocentric_elevation_angle_corrected(spa.e0, spa.del_e)

    spa.zenith = topocentric_zenith_angle(spa.e)
    spa.azimuth_astro = topocentric_azimuth_angle_astro(spa.h_prime, spa.latitude, spa.delta_prime)
    spa.azimuth = topocentric_azimuth_angle(spa.azimuth_astro)

    if (spa.function == SPA_ZA_INC) or (spa.function == SPA_ALL):
        spa.incidence = surface_incidence_angle(spa.zenith, spa.azimuth_astro, spa.azm_rotation, spa.slope)

    if (spa.function == SPA_ZA_RTS) or (spa.function == SPA_ALL):
        calculate_eot_and_sun_rise_transit_set(spa)

    return 0

# -----------------------------
# Convenience wrapper for plugin use
# -----------------------------

def spa_calculate_utc(
    dt_utc: datetime,
    latitude: float,
    longitude: float,
    elevation_m: float,
    pressure_mbar: float = 1013.25,
    temperature_c: float = 15.0,
    delta_t_s: float = 69.0,
    atmos_refract_deg: float = 0.5667,
) -> Tuple[float, float]:
    """Compute (azimuth_deg_from_north_clockwise, elevation_deg) for a UTC datetime."""
    if dt_utc.tzinfo is None:
        # Interpret naive datetimes as UTC (same convention as your previous spa_nrel.py)
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    else:
        dt_utc = dt_utc.astimezone(timezone.utc)

    spa = SpaData(
        year=dt_utc.year,
        month=dt_utc.month,
        day=dt_utc.day,
        hour=dt_utc.hour,
        minute=dt_utc.minute,
        second=dt_utc.second + dt_utc.microsecond/1e6,
        delta_ut1=0.0,
        delta_t=float(delta_t_s),
        timezone=0.0,
        longitude=float(longitude),
        latitude=float(latitude),
        elevation=float(elevation_m),
        pressure=float(pressure_mbar),
        temperature=float(temperature_c),
        slope=0.0,
        azm_rotation=0.0,
        atmos_refract=float(atmos_refract_deg),
        function=SPA_ZA,
    )
    rc = spa_calculate(spa)
    if rc != 0:
        raise ValueError(f"SPA input validation failed with code {rc}")
    # spa.azimuth is already "from north, clockwise" as returned by C version
    return spa.azimuth, spa.e

