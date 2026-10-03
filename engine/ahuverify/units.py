"""I-P <-> SI conversions, done once at the schema boundary (spec §4).

Every conversion is linear: value_SI = value × factor + offset.
SI units used inside the engine: °C, m, m², m/s, Pa, m³/s, kJ/kg dry air,
W, kg/s, fraction (0–1).
"""

from ahuverify.psychro import ip, si

# 1 Btu/lb = 2.326 kJ/kg exactly (International Table Btu).
_KJ_PER_KG_PER_BTU_PER_LB = 2.326
# 1 Btu/h = 0.29307107 W (IT Btu, 1055.05585262 J).
_W_PER_BTU_PER_H = 1055.05585262 / 3600.0
# Inch of water column at 39.2 °F (4 °C), the conventional value: 249.0889 Pa.
_PA_PER_IN_WC = 249.0889
_M_PER_FT = 0.3048
_KG_PER_LB = 0.45359237


def _dry_air_enthalpy_at_0f() -> float:
    """SI enthalpy (kJ/kg) of dry air at 0 °F, the I-P enthalpy datum.

    I-P enthalpy is zero for dry air at 0 °F; SI enthalpy is zero at 0 °C
    (ASHRAE Handbook — Fundamentals 2017, Ch. 1). From PsychroLib:
    1.006 kJ/kg·K × (−17.78 °C) = −17.884 kJ/kg.
    """
    return si.GetDryAirEnthalpy((0.0 - 32.0) * 5.0 / 9.0) / 1000.0


# unit -> (factor, offset) so that value_SI = value * factor + offset
_TO_SI: dict[str, tuple[float, float]] = {
    # temperature -> °C
    "C": (1.0, 0.0),
    "F": (5.0 / 9.0, -32.0 * 5.0 / 9.0),
    # length -> m
    "m": (1.0, 0.0),
    "ft": (_M_PER_FT, 0.0),
    # area -> m²
    "m2": (1.0, 0.0),
    "ft2": (_M_PER_FT**2, 0.0),
    # velocity -> m/s
    "m/s": (1.0, 0.0),
    "fpm": (_M_PER_FT / 60.0, 0.0),
    # pressure -> Pa
    "Pa": (1.0, 0.0),
    "in_wc": (_PA_PER_IN_WC, 0.0),
    # volumetric airflow -> m³/s
    "m3/s": (1.0, 0.0),
    "cfm": (_M_PER_FT**3 / 60.0, 0.0),
    "L/s": (0.001, 0.0),
    "m3/h": (1.0 / 3600.0, 0.0),
    # specific enthalpy -> kJ/kg dry air. The offset moves the I-P datum
    # (0 °F dry air) to the SI datum (0 °C dry air). Exact for dry air; for
    # moist air ASHRAE's rounded I-P and SI coefficients differ by up to
    # 0.03 Btu/lb at 100 °F. Use only for user-entered thresholds; display
    # values come from enthalpy_ip().
    "kJ/kg": (1.0, 0.0),
    "Btu/lb": (_KJ_PER_KG_PER_BTU_PER_LB, _dry_air_enthalpy_at_0f()),
    # power -> W
    "W": (1.0, 0.0),
    "kW": (1000.0, 0.0),
    "Btu/h": (_W_PER_BTU_PER_H, 0.0),
    "MBH": (1000.0 * _W_PER_BTU_PER_H, 0.0),
    # mass flow -> kg/s
    "kg/s": (1.0, 0.0),
    "kg/h": (1.0 / 3600.0, 0.0),
    "lb/h": (_KG_PER_LB / 3600.0, 0.0),
    # relative humidity / fraction -> 0–1
    "%": (0.01, 0.0),
}

SUPPORTED_UNITS = frozenset(_TO_SI)


def to_si(value: float, unit: str) -> float:
    """Convert a user-entered value in `unit` to the engine's SI unit."""
    factor, offset = _TO_SI[unit]
    return value * factor + offset


def from_si(value_si: float, unit: str) -> float:
    """Convert an engine SI value to `unit` (exact inverse of to_si)."""
    factor, offset = _TO_SI[unit]
    return (value_si - offset) / factor


def enthalpy_ip(t_db_c: float, w: float) -> float:
    """Moist-air enthalpy in Btu/lb dry air for display.

    Computed with PsychroLib in I-P mode from T (°F) and W:
    h = 0.240·T + W·(1061 + 0.444·T) (ASHRAE Fundamentals 2017, Ch. 1, Eq. 32).
    Never h_SI / 2.326: that factor is valid for enthalpy differences only.
    """
    return ip.GetMoistAirEnthalpy(from_si(t_db_c, "F"), w)
