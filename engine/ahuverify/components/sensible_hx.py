"""Sensible-only heat recovery: plate exchanger, runaround loop, heat pipe (spec §5.4).

Same supply/exhaust treatment as the energy wheel with ε_lat = 0 and no
carryover. Actuator `bypass` (0–1, default 0). A cold exhaust side can
condense or frost: that water is reported, and frost is flagged.
"""

from ahuverify import schema
from ahuverify.components import Check, ComponentResult, at_most, closure_residuals
from ahuverify.components._exchange import exchange
from ahuverify.state import AirStream


class SensibleHx:
    def __init__(self, name: str, cfg: schema.SensibleHx):
        self.name = name
        self.cfg = cfg
        self.type = cfg.type

    def solve(
        self, inlets: dict[str, AirStream], actuators: dict[str, float], p: float
    ) -> ComponentResult:
        supply, exhaust = inlets["supply_in"], inlets["exhaust_in"]
        x = exchange(
            supply, exhaust, self.cfg.eps_sens, 0.0, actuators.get("bypass", 0.0), p
        )
        checks = [Check("frost", x.exhaust_t_raw, 0.0, "C", not x.frost)]
        if self.cfg.face_area is not None and self.cfg.max_face_velocity is not None:
            v_face = supply.m_da * supply.state.v / self.cfg.face_area.si
            checks.append(
                at_most("face_velocity", v_face, self.cfg.max_face_velocity.si, "m/s")
            )
        return ComponentResult(
            outlets={"supply_out": x.supply_out, "exhaust_out": x.exhaust_out},
            loads={"condensate": x.condensate},
            checks=checks,
            residuals=closure_residuals(
                [supply, exhaust],
                [x.supply_out, x.exhaust_out],
                water_removed=x.condensate,
            ),
        )
