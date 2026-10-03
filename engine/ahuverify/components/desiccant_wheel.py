"""Desiccant wheel: black-box latent removal with a regeneration-heat penalty (spec §5.4).

LOW-CONFIDENCE PLACEHOLDER (docs/decisions/0004). At output u:
  process W_out = W_in·(1 − u·ε_lat)      (ε_lat = fraction of moisture removed)
  process h_out = h_in + u·Q_regen / m_s   (sensible penalty = regeneration heat)
  regen (exhaust) side takes the water at constant enthalpy, closing energy.
No regeneration heat, no drying: the `regen_heat` check fails if drying is
requested with Q_regen = 0.
"""

from ahuverify import schema
from ahuverify.components import Check, ComponentResult, closure_residuals
from ahuverify.state import AirStream, condense_to_saturation


class DesiccantWheel:
    type = "desiccant_wheel"

    def __init__(self, name: str, cfg: schema.DesiccantWheel):
        self.name = name
        self.cfg = cfg

    def solve(
        self, inlets: dict[str, AirStream], actuators: dict[str, float], p: float
    ) -> ComponentResult:
        supply, exhaust = inlets["supply_in"], inlets["exhaust_in"]
        u = actuators["output"]
        q_regen = u * self.cfg.regen_heat.si  # W
        removal = u * self.cfg.eps_lat if q_regen > 0 else 0.0
        s, e = supply.state, exhaust.state
        w_s = s.w * (1.0 - removal)
        h_s = s.h + q_regen / 1000.0 / supply.m_da
        water = supply.m_da * (s.w - w_s)
        s_state, c_s = condense_to_saturation(h_s, w_s, p)
        e_state, c_e = condense_to_saturation(e.h, e.w + water / exhaust.m_da, p)
        supply_out, exhaust_out = (
            AirStream(s_state, supply.m_da),
            AirStream(e_state, exhaust.m_da),
        )
        condensate = c_s * supply.m_da + c_e * exhaust.m_da
        regen_ok = u == 0.0 or self.cfg.regen_heat.si > 0.0
        return ComponentResult(
            outlets={"supply_out": supply_out, "exhaust_out": exhaust_out},
            loads={
                "q_regen": q_regen,
                "water_removed": water,
                "condensate": condensate,
            },
            checks=[Check("regen_heat", self.cfg.regen_heat.si, 0.0, "W", regen_ok)],
            residuals=closure_residuals(
                [supply, exhaust],
                [supply_out, exhaust_out],
                water_removed=condensate,
                heat_added=q_regen,
            ),
        )
