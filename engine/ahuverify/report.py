"""Results in display units, ready for JSON (spec §8: web displays, never computes).

Every number the web app shows comes from here, already in I-P or SI.
I-P enthalpy uses I-P equations (units.enthalpy_ip), never h_SI / 2.326.
"""

import math

from ahuverify import units

UNIT_SYSTEMS = ("ip", "si")

STATE_UNITS = {
    "ip": {
        "db": "°F",
        "wb": "°F",
        "dp": "°F",
        "rh": "%",
        "w": "gr/lb",
        "h": "Btu/lb",
        "v": "ft³/lb",
        "flow": "cfm",
    },
    "si": {
        "db": "°C",
        "wb": "°C",
        "dp": "°C",
        "rh": "%",
        "w": "g/kg",
        "h": "kJ/kg",
        "v": "m³/kg",
        "flow": "m³/s",
    },
}
# engine SI unit -> (I-P display unit, SI display unit); labels as shown to people
_DISPLAY = {
    "C": (("F", "°F"), ("C", "°C")),
    "m/s": (("fpm", "fpm"), ("m/s", "m/s")),
    "m3/s": (("cfm", "cfm"), ("m3/s", "m³/s")),
    "kg/s": (("lb/h", "lb/h"), ("kg/h", "kg/h")),
    "kg/kg": (("gr/lb", "gr/lb"), ("g/kg", "g/kg")),
    "W": (("MBH", "MBH"), ("kW", "kW")),
}


def _temperature(t_c: float, system: str) -> float:
    return units.from_si(t_c, "F") if system == "ip" else t_c


def state_row(key: str, stream, system: str) -> dict:
    """One state as display numbers: db, wb, dp, rh, w, h, v and volumetric flow."""
    s = stream.state
    ip = system == "ip"
    return {
        "key": key,
        "db": _temperature(s.t_db, system),
        "wb": _temperature(s.t_wb, system),
        "dp": _temperature(s.t_dp, system),
        "rh": s.rh * 100.0,
        "w": units.from_si(s.w, "gr/lb" if ip else "g/kg"),
        "h": units.enthalpy_ip(s.t_db, s.w) if ip else s.h,
        "v": units.from_si(s.v, "ft3/lb" if ip else "m3/kg"),
        "flow": units.from_si(stream.m_da * s.v, "cfm" if ip else "m3/s"),
        "m_da": units.from_si(stream.m_da, "lb/h" if ip else "kg/s"),
    }


def display(value: float, si_unit: str, system: str) -> tuple[float | None, str]:
    """(value, unit label) in the chosen system. Fractions ("-") become %."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None, ""
    if si_unit == "-":
        return value * 100.0, "%"
    if si_unit not in _DISPLAY:
        return value, si_unit
    (unit, label) = _DISPLAY[si_unit][0 if system == "ip" else 1]
    return units.from_si(value, unit), label


def _load_unit(name: str) -> str:
    if name.startswith("q_") or name == "power":
        return "W"
    if name in ("adp", "chwr_implied"):
        return "C"
    if name in ("shr", "bf"):
        return "-"
    return "kg/s"  # flows of air or water


def component_report(result, system: str) -> dict:
    loads = {}
    for name, value in result.loads.items():
        v, label = display(value, _load_unit(name), system)
        loads[name] = {"value": v, "unit": label}
    checks = []
    for c in result.checks:
        v, label = display(c.value, c.unit, system)
        lim, _ = display(c.limit, c.unit, system)
        checks.append(
            {
                "name": c.name,
                "value": v,
                "limit": lim,
                "unit": label,
                "passed": c.passed,
            }
        )
    return {"loads": loads, "checks": checks}


def failure_report(f) -> dict:
    return {
        "kind": f.kind.value,
        "severity": f.severity,
        "message": f.message,
        "component": f.component,
        "mode": f.mode,
        "condition_id": f.condition_id,
        "value": f.value,
        "limit": f.limit,
    }


def condition_report(cr, system: str) -> dict:
    """An analysis.ConditionResult as a JSON-ready dict in display units."""
    if system not in UNIT_SYSTEMS:
        raise ValueError(f"Unit system must be one of {UNIT_SYSTEMS}.")
    r = cr.result
    return {
        "condition_id": cr.condition_id,
        "mode": cr.mode,
        "units": STATE_UNITS[system],
        "valid": r.valid if r else False,
        "positions": cr.positions,
        "states": [state_row(k, s, system) for k, s in r.states.items()] if r else [],
        "components": {n: component_report(c, system) for n, c in r.components.items()}
        if r
        else {},
        "failures": [failure_report(f) for f in cr.failures],
    }
