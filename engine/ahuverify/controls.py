"""Controls: mode selection, fixed positions, staged loops (spec §5.6).

Conditions are structured data, evaluated here by explicit code — no
string expressions, no eval.
"""

import operator
from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import pairwise

from ahuverify import failures, schema, units
from ahuverify.failures import Failure
from ahuverify.lanes import CompiledUnit, ConfigError
from ahuverify.solver import SolveResult, oa_damper_flow, solve
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


# ---------- actuators ----------

MIN_OA = "min_oa"  # position that gives the configured minimum OA at the OA damper

# type -> actuator -> (off end, default when neither fixed nor in an active loop)
_ACTUATORS: dict[str, dict[str, tuple]] = {
    "mixing_box": {"oa_fraction": (MIN_OA, MIN_OA)},
    "heating_coil_hw": {"valve": (0.0, 0.0)},
    "cooling_coil_chw": {"valve": (0.0, 0.0)},
    "electric_heater": {"output": (0.0, 0.0)},
    "steam_humidifier": {"output": (0.0, 0.0)},
    "adiabatic_humidifier": {"output": (0.0, 0.0)},
    "desiccant_wheel": {"output": (0.0, 0.0)},
    # A wheel nobody controls keeps running; its off end is stopped / bypassed.
    "energy_wheel": {"bypass": (1.0, 0.0), "speed": (0.0, 1.0)},
    "plate_hx": {"bypass": (1.0, 0.0)},
    "runaround": {"bypass": (1.0, 0.0)},
    "heat_pipe": {"bypass": (1.0, 0.0)},
}


def actuator_table(cfg: schema.UnitConfig) -> dict[str, tuple]:
    """Every actuator in the unit: "comp.actuator" -> (off end, default)."""
    out = {}
    for name, model in cfg.components.items():
        if model.type == "cooling_coil_chw" and model.mode == "measured":
            continue  # forced leaving state, nothing to move
        for act, ends in _ACTUATORS.get(model.type, {}).items():
            out[f"{name}.{act}"] = ends
    return out


def min_oa_position(
    unit: CompiledUnit, oa: AirState, ra: AirState, positions: dict[str, float]
) -> float:
    """OA damper position giving the configured minimum OA at the OA damper.

    Q_OA is nearly proportional to position, so iterate f <- f · Q_min / Q(f)
    from f = Q_min / Q_supply until within 0.001 % (a few solves).
    """
    q_min = unit.cfg.airflows.min_oa.si
    ref = f"{unit.mixing_box}.oa_fraction"
    if q_min <= 0.0:
        return 0.0
    f = min(q_min / unit.cfg.airflows.supply.si, 1.0)
    for _ in range(10):
        q = oa_damper_flow(unit, solve(unit, oa, ra, {**positions, ref: f}))
        if q <= 0.0 or abs(q / q_min - 1.0) < 1e-5:
            break
        f_new = min(f * q_min / q, 1.0)
        if f_new == f:
            break
        f = f_new
    return f


# ---------- one staged loop (spec §5.6 steps 1–4) ----------

PV_TOL = 0.01  # K
_MONOTONIC_EPS = 1e-6  # K


@dataclass
class LoopOutcome:
    positions: dict[str, float]
    pv: float
    failure: Failure | None = None


def solve_staged_loop(
    loop: str,
    stages: list[str],
    pv: Callable[[dict[str, float]], float],
    setpoint: float,
    positions: dict[str, float],
    ends: dict[str, tuple[float, float]],
    *,
    sensor: str = "the sensed value",
    tol: float = PV_TOL,
) -> LoopOutcome:
    """Staged solve: stages start at their off end; each stage in turn either
    brackets the setpoint (then bisect and stop) or parks at the end nearer
    the setpoint. ends[stage] = (off, on). The sensed value must move one way
    over the stroke (sign check at 5 points) or NON_MONOTONIC is returned."""
    pos = dict(positions)
    for s in stages:
        pos[s] = ends[s][0]
    value = pv(pos)
    for s in stages:
        off, on = ends[s]
        us = [off + k * (on - off) / 4 for k in range(5)]
        pvs = [pv({**pos, s: u}) for u in us]
        steps = [b - a for a, b in pairwise(pvs)]
        if any(d > _MONOTONIC_EPS for d in steps) and any(
            d < -_MONOTONIC_EPS for d in steps
        ):
            return LoopOutcome(pos, value, failures.non_monotonic(loop, sensor, s))
        lo_pv, hi_pv = min(pvs[0], pvs[-1]), max(pvs[0], pvs[-1])
        if lo_pv - tol <= setpoint <= hi_pv + tol:
            pos[s], value = _bisect_stage(pv, pos, s, us, pvs, setpoint, tol)
            return LoopOutcome(pos, value)
        nearer = 0 if abs(pvs[0] - setpoint) <= abs(pvs[-1] - setpoint) else -1
        pos[s], value = us[nearer], pvs[nearer]
    last = stages[-1]
    return LoopOutcome(
        pos,
        value,
        failures.setpoint_not_met(loop, sensor, last, pos[last], value, setpoint),
    )


def _bisect_stage(pv, pos, stage, us, pvs, setpoint, tol) -> tuple[float, float]:
    """Bisect the stage position to within tol of setpoint (max 60 iterations)."""
    for u, v in zip(us, pvs):
        if abs(v - setpoint) <= tol:
            return u, v
    k = next(k for k in range(4) if (pvs[k] - setpoint) * (pvs[k + 1] - setpoint) <= 0)
    a, fa, b = us[k], pvs[k] - setpoint, us[k + 1]
    mid, v = a, pvs[k]
    for _ in range(60):
        mid = 0.5 * (a + b)
        v = pv({**pos, stage: mid})
        if abs(v - setpoint) <= tol:
            break
        if fa * (v - setpoint) <= 0:
            b = mid
        else:
            a, fa = mid, v - setpoint
    return mid, v


# ---------- a whole condition: mode, fixed positions, loops ----------

MAX_LOOP_PASSES = 20
_MOVE_TOL = 0.001


@dataclass
class ConditionOutcome:
    mode: str | None
    positions: dict[str, float]
    result: SolveResult | None
    failures: list[Failure] = field(default_factory=list)


def run_condition(
    unit: CompiledUnit, cfg: schema.UnitConfig, i: ConditionInputs
) -> ConditionOutcome:
    """Select the mode, apply defaults and fixed positions, solve the mode's
    loops in declared order, repeating until no actuator moves > 0.001."""
    mode = select_mode(cfg.sequence.modes, i)
    if mode is None:
        return ConditionOutcome(
            None, {}, None, [failures.no_active_mode(i.oa.t_db, i.oa.rh, i.schedule)]
        )
    table = actuator_table(cfg)
    for ref in mode.fixed:
        if ref not in table:
            raise ConfigError(
                f"Mode {mode.id} fixes {ref}, which is not an actuator in this unit."
            )
    memo: dict[tuple, SolveResult] = {}

    def run(pos: dict[str, float]) -> SolveResult:
        key = tuple(sorted(pos.items()))
        if key not in memo:
            memo[key] = solve(unit, i.oa, i.ra, pos)
        return memo[key]

    oa_ref = f"{unit.mixing_box}.oa_fraction" if unit.mixing_box else None
    loops = [(lid, cfg.sequence.loops[lid]) for lid in mode.loops]
    staged = {s.actuator for _, lp in loops for s in lp.stages}
    sensors = {s.id: s.at for s in cfg.sensors}
    positions = {
        ref: (0.0 if d == MIN_OA else d) for ref, (_, d) in table.items()
    } | dict(mode.fixed)

    loop_failures: dict[str, Failure | None] = {}
    previous = None
    passes = 0
    for passes in range(1, MAX_LOOP_PASSES + 1):
        f_min = 0.0
        if oa_ref and oa_ref not in mode.fixed:
            f_min = min_oa_position(unit, i.oa, i.ra, positions)
            if oa_ref not in staged:
                positions[oa_ref] = f_min
        ends = {ref: _ends(table[ref][0], f_min) for ref in staged}
        for lid, lp in loops:
            loc = sensors[lp.sensor]
            out = solve_staged_loop(
                lid,
                [s.actuator for s in lp.stages],
                lambda pos, loc=loc: run(pos).states[loc].state.t_db,
                lp.setpoint.si,
                positions,
                ends,
                sensor=lp.sensor,
            )
            positions, loop_failures[lid] = out.positions, out.failure
        if (
            previous
            and max(abs(positions[k] - previous[k]) for k in positions) <= _MOVE_TOL
        ):
            break
        previous = dict(positions)
    else:
        loop_failures["_passes"] = failures.loops_not_converged(mode.id, passes)

    result = run(positions)
    found = [f for f in loop_failures.values() if f is not None] + list(result.failures)
    return ConditionOutcome(mode.id, positions, result, found)


def _ends(off, f_min: float) -> tuple[float, float]:
    """(off, on) for a stage: valves 0 -> 1, bypass 1 -> 0, OA damper min -> 1."""
    if off == MIN_OA:
        return (f_min, 1.0)
    return (off, 1.0 - off)
