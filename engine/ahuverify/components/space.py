"""Space node: closes the loop from supply air to return air (spec §5.4, §5.5)."""

from ahuverify import schema
from ahuverify.components import ComponentResult, at_least, at_most, closure_residuals
from ahuverify.psychro import si
from ahuverify.state import AirStream, condense_to_saturation


def vapor_enthalpy(t_db: float) -> float:
    """Enthalpy of water vapor in moist air, kJ/kg: ∂h/∂W from PsychroLib (2501 + 1.86·T)."""
    return (
        si.GetMoistAirEnthalpy(t_db, 1.0) - si.GetMoistAirEnthalpy(t_db, 0.0)
    ) / 1000.0


class Space:
    type = "space"

    def __init__(self, name: str, cfg: schema.Space):
        self.name = name
        self.cfg = cfg

    def solve(
        self, inlets: dict[str, AirStream], actuators: dict[str, float], p: float
    ) -> ComponentResult:
        """Room state from supply air plus loads, on the supply dry-air flow.

        h_room = h_sa + (q_sens + q_lat) / m_sa;  W_room = W_sa + moisture / m_sa.
        A latent load given as heat becomes moisture = q_lat / h_g(T_room)
        (iterated on T_room). Air leaving as exfiltration (supply − return) is
        at the room state, so it does not change the room balance.
        """
        sa = inlets["in"]
        m = sa.m_da
        q_s = self.cfg.sensible_load.si
        h = sa.state.h + q_s / 1000.0 / m
        t_room = sa.state.t_db
        moisture = (
            self.cfg.moisture_load.si if self.cfg.moisture_load is not None else 0.0
        )
        q_l = 0.0
        if self.cfg.latent_load is not None:
            q_l = self.cfg.latent_load.si
            for _ in range(4):
                moisture = q_l / 1000.0 / vapor_enthalpy(t_room)
                t_room = si.GetTDryBulbFromEnthalpyAndHumRatio(
                    (h + q_l / 1000.0 / m) * 1000.0, sa.state.w + moisture / m
                )
        else:
            q_l = moisture * vapor_enthalpy(t_room) * 1000.0
        state, condensate = condense_to_saturation(
            h + q_l / 1000.0 / m, sa.state.w + moisture / m, p
        )
        out = AirStream(state, m)
        checks = []
        if self.cfg.t_min is not None:
            checks.append(at_least("t_min", state.t_db, self.cfg.t_min.si, "C"))
        if self.cfg.t_max is not None:
            checks.append(at_most("t_max", state.t_db, self.cfg.t_max.si, "C"))
        if self.cfg.rh_max is not None:
            checks.append(at_most("rh_max", state.rh, self.cfg.rh_max.si, "-"))
        return ComponentResult(
            outlets={"out": out},
            loads={
                "q_sens": q_s,
                "q_lat": q_l,
                "moisture": moisture,
                "condensate": condensate * m,
            },
            checks=checks,
            residuals=closure_residuals(
                [sa],
                [out],
                water_added=moisture,
                water_removed=condensate * m,
                heat_added=q_s + q_l,
            ),
        )
