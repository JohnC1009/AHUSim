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
