"""Steam humidifier: isothermal humidification (spec §5.4)."""

from ahuverify import schema
from ahuverify.components import ComponentResult, at_most, closure_residuals
from ahuverify.psychro import si
from ahuverify.state import AirState, AirStream


class SteamHumidifier:
    type = "steam_humidifier"

    def __init__(self, name: str, cfg: schema.SteamHumidifier):
        self.name = name
        self.cfg = cfg

    def solve(
        self, inlets: dict[str, AirStream], actuators: dict[str, float], p: float
    ) -> ComponentResult:
        """W_out = W_in + output·max_rate / m_da at constant T, capped at saturation.

        Isothermal: steam humidification raises W with negligible change in
        dry bulb (ASHRAE Handbook — HVAC Systems and Equipment, Ch. 22). The
        steam's energy is the enthalpy rise of the air. If the air cannot
        absorb the requested steam, W stops at saturation and the
        `saturation` check fails (steam would condense in the duct).
        """
        inlet = inlets["in"]
        s = inlet.state
        requested = actuators["output"] * self.cfg.max_rate.si  # kg/s
        w_target = s.w + requested / inlet.m_da
        w_sat = si.GetSatHumRatio(s.t_db, p)
        out = AirStream(AirState(s.t_db, min(w_target, w_sat), p), inlet.m_da)
        absorbed = inlet.m_da * (out.state.w - s.w)
        steam_energy = inlet.m_da * (out.state.h - s.h) * 1000.0  # W
        return ComponentResult(
            outlets={"out": out},
            loads={"steam": absorbed, "q_total": steam_energy},
            checks=[at_most("saturation", w_target, w_sat, "kg/kg")],
            residuals=closure_residuals(
                [inlet], [out], water_added=absorbed, heat_added=steam_energy
            ),
        )
