"""Electric duct heater: sensible heat, constant W (spec §5.4)."""

import math

from ahuverify import schema
from ahuverify.components import ComponentResult, closure_residuals
from ahuverify.state import AirState, AirStream


def staged_output(output: float, stages: int | None) -> float:
    """Delivered fraction of rated power.

    Modulating (SCR, stages None): the command itself. Staged: stage k of N
    is on when output ≥ k/N, so delivered = floor(output·N)/N. A staged
    heater can therefore miss a setpoint by up to one stage.
    """
    if stages is None:
        return output
    return math.floor(output * stages + 1e-9) / stages


class ElectricHeater:
    type = "electric_heater"

    def __init__(self, name: str, cfg: schema.ElectricHeater):
        self.name = name
        self.cfg = cfg

    def solve(
        self, inlets: dict[str, AirStream], actuators: dict[str, float], p: float
    ) -> ComponentResult:
        inlet = inlets["in"]
        q = staged_output(actuators["output"], self.cfg.stages) * self.cfg.power.si  # W
        s = inlet.state
        out = AirStream(
            AirState.from_h_w(s.h + q / 1000.0 / inlet.m_da, s.w, p), inlet.m_da
        )
        return ComponentResult(
            outlets={"out": out},
            loads={"q_total": q, "q_sens": q},
            residuals=closure_residuals([inlet], [out], heat_added=q),
        )
