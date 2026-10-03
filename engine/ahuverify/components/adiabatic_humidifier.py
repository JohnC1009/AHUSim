"""Adiabatic (evaporative) humidifier: toward the wet bulb at constant enthalpy (spec §5.4)."""

from ahuverify import schema
from ahuverify.components import ComponentResult, at_most, closure_residuals
from ahuverify.psychro import si
from ahuverify.state import AirState, AirStream


class AdiabaticHumidifier:
    type = "adiabatic_humidifier"

    def __init__(self, name: str, cfg: schema.AdiabaticHumidifier):
        self.name = name
        self.cfg = cfg

    def solve(
        self, inlets: dict[str, AirStream], actuators: dict[str, float], p: float
    ) -> ComponentResult:
        """T_out = T_in − output·ε·(T_in − T_wb) along constant h; W from (h, T).

        Evaporative cooling follows a line of (nearly) constant enthalpy toward
        the wet bulb (ASHRAE Fundamentals 2017, Ch. 1, adiabatic saturation).
        If the water needed exceeds max_rate, W is limited to
        W_in + max_rate / m_da (still at constant h) and the `rate` check fails.
        """
        inlet = inlets["in"]
        s = inlet.state
        t_target = s.t_db - actuators["output"] * self.cfg.effectiveness * (
            s.t_db - s.t_wb
        )
        w_target = si.GetHumRatioFromEnthalpyAndTDryBulb(s.h * 1000.0, t_target)
        requested = inlet.m_da * (w_target - s.w)
        w = min(w_target, s.w + self.cfg.max_rate.si / inlet.m_da)
        out = AirStream(AirState.from_h_w(s.h, w, p), inlet.m_da)
        added = inlet.m_da * (w - s.w)
        return ComponentResult(
            outlets={"out": out},
            loads={"water": added},
            checks=[at_most("rate", requested, self.cfg.max_rate.si, "kg/s")],
            residuals=closure_residuals([inlet], [out], water_added=added),
        )
