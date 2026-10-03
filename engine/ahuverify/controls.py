"""Controls: mode selection, fixed positions, staged loops (spec §5.6).

Conditions are structured data, evaluated here by explicit code — no
string expressions, no eval.
"""

import operator
from dataclasses import dataclass

from ahuverify import schema, units
from ahuverify.state import AirState

_OPS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
}


@dataclass(frozen=True)
class ConditionInputs:
    """What mode conditions can look at. space_t (°C) defaults to the
    return-air dry bulb when not given (return air stands in for the room)."""

    oa: AirState
    ra: AirState
    schedule: str | None = None
    space_t: float | None = None


def _enthalpy(state: AirState, unit: str) -> float:
    """Enthalpy in the threshold's own unit: Btu/lb from I-P equations, else kJ/kg."""
    return units.enthalpy_ip(state.t_db, state.w) if unit == "Btu/lb" else state.h


def _compare(c: schema.Comparison, i: ConditionInputs) -> bool:
    op = _OPS[c.op]
    if c.var == "schedule":
        return i.schedule is not None and op(i.schedule, c.value)
    if c.var in ("oa_h", "ra_h"):
        state = i.oa if c.var == "oa_h" else i.ra
        return op(
            _enthalpy(state, c.value.unit),
            c.value.value if c.value.unit == "Btu/lb" else c.value.si,
        )
    lhs = {
        "oa_db": i.oa.t_db,
        "oa_dp": i.oa.t_dp,
        "ra_db": i.ra.t_db,
        "space_t": i.ra.t_db if i.space_t is None else i.space_t,
    }[c.var]
    return op(lhs, c.value.si)


def evaluate(cond: schema.Condition, i: ConditionInputs) -> bool:
    """True if the structured condition holds for these inputs."""
    if isinstance(cond, schema.AllOf):
        return all(evaluate(c, i) for c in cond.all)
    if isinstance(cond, schema.AnyOf):
        return any(evaluate(c, i) for c in cond.any)
    if isinstance(cond, schema.NotOf):
        return not evaluate(cond.not_, i)
    return _compare(cond, i)


def select_mode(modes: list[schema.Mode], i: ConditionInputs) -> schema.Mode | None:
    """First mode, in ascending priority number, whose enter condition is true.
    Equal priorities keep their declared order. None if no mode is active."""
    for mode in sorted(modes, key=lambda m: m.priority):
        if evaluate(mode.enter, i):
            return mode
    return None
