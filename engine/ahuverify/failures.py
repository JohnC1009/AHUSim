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
