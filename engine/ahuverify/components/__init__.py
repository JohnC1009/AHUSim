"""Component interface, results and mass/water/energy closure (spec §5.2, §5.3).

Each component module builds from its schema model (reading SI via `.si`)
and implements solve(inlets, actuators, p) -> ComponentResult.
Ports: single-lane `in`/`out`; cross-lane `supply_in`, `supply_out`,
`exhaust_in`, `exhaust_out`; mixing box `oa`, `ra`, `mixed`, `relief`.
"""

from dataclasses import dataclass, field

from ahuverify.state import AirStream

# Residual limit: every closure must be below 0.1 % relative (spec §5.3).
RESIDUAL_LIMIT = 1e-3


@dataclass(frozen=True)
class Check:
    """A limit check. value and limit in SI; passed is the verdict."""

    name: str
    value: float
    limit: float
    unit: str
    passed: bool


@dataclass
class ComponentResult:
    outlets: dict[str, AirStream]
    loads: dict[str, float] = field(default_factory=dict)  # W; kg/s for flows
    checks: list[Check] = field(default_factory=list)
    residuals: dict[str, float] = field(default_factory=dict)


# A check passes within 0.01 % of its limit: a value that a search set onto the
# limit is not failed by round-off (0.3 cfm at 3,000 cfm, 0.15 fpm at 1,500 fpm).
CHECK_TOLERANCE = 1e-4


def at_most(name: str, value: float, limit: float, unit: str) -> Check:
    return Check(
        name, value, limit, unit, value <= limit + CHECK_TOLERANCE * abs(limit)
    )


def at_least(name: str, value: float, limit: float, unit: str) -> Check:
    return Check(
        name, value, limit, unit, value >= limit - CHECK_TOLERANCE * abs(limit)
    )


def closure_residuals(
    inlets: list[AirStream],
    outlets: list[AirStream],
    *,
    water_added: float = 0.0,
    water_removed: float = 0.0,
    heat_added: float = 0.0,
) -> dict[str, float]:
    """Relative closure of dry air, water and energy for one component.

    dry air:  (Σ m_in − Σ m_out) / Σ m_in
    water:    (Σ m·W in + water added − Σ m·W out − water removed) / (Σ m·W in + water added)
    energy:   (Σ m·h in + heat added − Σ m·h out) / scale
    Water flows in kg/s, heat in W (positive into the air). Removed water
    (condensate) carries zero enthalpy, consistent with condense_to_saturation.
    The energy scale is the larger of Σ|m·h| in and out, and never less than
    Σ m_in × 1 kJ/kg, because h is near zero for winter air on the 0 °C datum.
    """
    m_in = sum(s.m_da for s in inlets)
    m_out = sum(s.m_da for s in outlets)
    w_in = sum(s.m_da * s.state.w for s in inlets) + water_added
    w_out = sum(s.m_da * s.state.w for s in outlets) + water_removed
    e_in = sum(s.m_da * s.state.h for s in inlets) + heat_added / 1000.0  # kW
    e_out = sum(s.m_da * s.state.h for s in outlets)
    e_scale = max(
        sum(abs(s.m_da * s.state.h) for s in inlets) + abs(heat_added) / 1000.0,
        sum(abs(s.m_da * s.state.h) for s in outlets),
        m_in * 1.0,
    )
    return {
        "dry_air": (m_in - m_out) / m_in if m_in else 0.0,
        "water": (w_in - w_out) / w_in if w_in else 0.0,
        "energy": (e_in - e_out) / e_scale if e_scale else 0.0,
    }
