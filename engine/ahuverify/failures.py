"""Failure types (spec §5.7). Messages: one plain sentence with numbers and units."""

from dataclasses import dataclass
from enum import StrEnum


class FailureKind(StrEnum):
    SETPOINT_NOT_MET = "setpoint_not_met"
    LIMIT_EXCEEDED = "limit_exceeded"  # face velocity, rate, frost
    MODE_GAP = "mode_gap"
    MODE_OVERLAP = "mode_overlap"
    CONFIG_ERROR = "config_error"  # missing sensor/actuator, bad topology
    FIGHTING = "fighting"  # simultaneous heat+cool; economizer with h_oa > h_ra
    CANNOT_COMPUTE = "cannot_compute"  # required input missing
    NON_MONOTONIC = "non_monotonic"
    NON_CONVERGED = "non_converged"
    ENGINE_RESIDUAL = "engine_residual"


@dataclass(frozen=True)
class Failure:
    kind: FailureKind
    message: str
    component: str | None = None  # component id or loop id
    mode: str | None = None
    condition_id: str | None = None
    value: float | None = None
    limit: float | None = None


# --- Message builders: one plain I-P sentence with numbers and units. ---
# value/limit stay SI so a UI can show either unit system.


def _f(t_c: float) -> str:
    return f"{t_c * 1.8 + 32:.1f} °F"


def _df(dt_k: float) -> str:
    return f"{abs(dt_k) * 1.8:.1f} °F"


def setpoint_not_met(
    loop: str, sensor: str, stage: str, position: float, pv: float, sp: float
) -> Failure:
    return Failure(
        FailureKind.SETPOINT_NOT_MET,
        f"Loop {loop} cannot hold {sensor} at {_f(sp)}: with {stage} at {position * 100:.0f} % "
        f"{sensor} is {_f(pv)}, {_df(pv - sp)} {'above' if pv > sp else 'below'} setpoint.",
        component=loop,
        value=pv,
        limit=sp,
    )


def non_monotonic(loop: str, sensor: str, stage: str) -> Failure:
    return Failure(
        FailureKind.NON_MONOTONIC,
        f"Loop {loop}: {sensor} does not move steadily one way as {stage} strokes, "
        f"so no single position can be trusted to hold setpoint.",
        component=loop,
    )


def loops_not_converged(mode: str, passes: int) -> Failure:
    return Failure(
        FailureKind.NON_CONVERGED,
        f"The control loops in mode {mode} kept moving after {passes} passes (more than 0.1 % per pass).",
        mode=mode,
    )


def no_active_mode(oa_t: float, oa_rh: float, schedule: str | None) -> Failure:
    sched = f" with schedule = {schedule}" if schedule else ""
    return Failure(
        FailureKind.MODE_GAP,
        f"No mode is active at OA {_f(oa_t)} / {oa_rh * 100:.0f} % RH{sched}.",
    )


# --- Component limit checks -> LIMIT_EXCEEDED (or CONFIG_ERROR) ---

_PORT = {"oa": "outdoor-air damper", "ra": "return damper", "relief": "relief damper"}
_LABEL = {
    "heating_coil_hw": "Heating coil",
    "cooling_coil_chw": "Cooling coil",
    "plate_hx": "Heat exchanger",
    "runaround": "Runaround loop",
    "heat_pipe": "Heat pipe",
}


def _fpm(v: float) -> str:
    return f"{v / (0.3048 / 60):,.0f} fpm"


def _cfm(q: float) -> str:
    return f"{q / (0.3048**3 / 60):,.0f} cfm"


def _lbh(m: float) -> str:
    return f"{m * 3600 / 0.45359237:,.0f} lb/h"


def from_check(component: str, component_type: str, check) -> Failure:
    """A failed component check as one plain I-P sentence (value/limit stay SI)."""
    name, v, lim = check.name, check.value, check.limit
    kind = FailureKind.LIMIT_EXCEEDED
    where = component
    if name.startswith("face_velocity_"):
        port = name.removeprefix("face_velocity_")
        where = f"{component}.{port}"
        msg = f"The {_PORT[port]} {where} runs at {_fpm(v)}, above its {_fpm(lim)} maximum."
    elif name == "face_velocity":
        msg = f"{_LABEL.get(component_type, 'Component')} {component} has a face velocity of {_fpm(v)}, above its {_fpm(lim)} maximum."
    elif name == "min_oa":
        where = f"{component}.min_oa"
        msg = f"Outdoor air at {component} is {_cfm(v)}, below the {_cfm(lim)} minimum."
    elif name == "pressurization_bias":
        where = f"{component}.pressurization_bias"
        msg = (
            f"Outdoor air at {component} is below the pressurization bias, so return air must rise "
            f"{(lim / v - 1) * 100:.0f} % above design and the building loses its pressurization."
        )
    elif name == "mixed_air_freeze":
        msg = f"Mixed air at {component} is {_f(v)}, below its {_f(lim)} freeze threshold."
    elif name == "airflow":
        msg = f"Fan {component} moves {_cfm(v)}, above its {_cfm(lim)} design airflow."
    elif name == "frost":
        msg = f"Exhaust air leaving {component} would be {_f(v)} and saturated, so {component} will frost."
    elif name == "saturation":
        msg = f"Humidifier {component} is asked for more steam than the air can absorb, so the duct downstream would get wet."
    elif name == "rate":
        msg = f"Humidifier {component} needs {_lbh(v)} of water, above its {_lbh(lim)} maximum."
    elif name == "regen_heat":
        msg = f"Desiccant wheel {component} is asked to dry air with no regeneration heat."
    elif name == "reachable":
        kind = FailureKind.CONFIG_ERROR
        msg = f"The measured leaving state of {component} has more moisture or energy than the entering air, which no cooling coil can produce."
    elif name in ("t_min", "t_max"):
        side = "below its minimum" if name == "t_min" else "above its maximum"
        msg = f"Space {component} is {_f(v)}, {side} of {_f(lim)}."
    elif name == "rh_max":
        msg = f"Space {component} is at {v * 100:.0f} % RH, above its {lim * 100:.0f} % maximum."
    else:
        msg = f"{component}: {name} is {v:.4g} {check.unit} against a limit of {lim:.4g} {check.unit}."
    return Failure(kind, msg, component=where, value=v, limit=lim)


def fighting_heat_cool(
    heater: str, heat_pos: float, cooler: str, cool_pos: float
) -> Failure:
    return Failure(
        FailureKind.FIGHTING,
        f"{heater} heats ({heat_pos * 100:.0f} % open) upstream of {cooler}, which is cooling "
        f"({cool_pos * 100:.0f} % open), so the two fight each other.",
        component=heater,
        value=heat_pos,
    )


def fighting_economizer(
    box: str, pos: float, f_min: float, h_oa_ip: float, h_ra_ip: float
) -> Failure:
    return Failure(
        FailureKind.FIGHTING,
        f"Economizer {box} is open to {pos * 100:.0f} % (minimum {f_min * 100:.0f} %) while outdoor air "
        f"at {h_oa_ip:.1f} Btu/lb carries more enthalpy than return air at {h_ra_ip:.1f} Btu/lb.",
        component=box,
        value=pos,
        limit=f_min,
    )
