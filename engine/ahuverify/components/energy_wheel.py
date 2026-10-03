"""Energy (enthalpy) wheel: sensible and latent recovery between lanes (spec §5.4).

Actuators: `bypass` (0–1, default 0) and `speed` (0–1, default 1). Speed
scales both effectivenesses linearly (assumption, docs/decisions/0004).
EATR: modelled as an equal-mass swap at the inlets — a fraction EATR of the
supply flow is replaced by exhaust-inlet air and the same mass of outdoor air
joins the exhaust side — so each side keeps its dry-air flow and energy is
conserved. `purge` is recorded but has no separate effect: the entered EATR
is taken to already reflect the purge sector.
"""

from ahuverify import schema
from ahuverify.components import Check, ComponentResult, closure_residuals
from ahuverify.components._exchange import exchange
from ahuverify.components.mixing_box import mix_airstreams
from ahuverify.state import AirStream


def carryover_swap(
    supply: AirStream, exhaust: AirStream, eatr: float, p: float
) -> tuple[AirStream, AirStream, float]:
    """Swap m_t = EATR·m_supply between the two inlets (exhaust → supply, OA → exhaust)."""
    if eatr <= 0.0:
        return supply, exhaust, 0.0
    m_t = eatr * supply.m_da
    if m_t > exhaust.m_da:
        raise ValueError("EATR transfer exceeds the exhaust airflow.")
    s, c1 = mix_airstreams(
        [AirStream(supply.state, supply.m_da - m_t), AirStream(exhaust.state, m_t)], p
    )
    e, c2 = mix_airstreams(
        [AirStream(exhaust.state, exhaust.m_da - m_t), AirStream(supply.state, m_t)], p
    )
    return s, e, c1 + c2


class EnergyWheel:
    type = "energy_wheel"

    def __init__(self, name: str, cfg: schema.EnergyWheel):
        self.name = name
        self.cfg = cfg

    def solve(
        self, inlets: dict[str, AirStream], actuators: dict[str, float], p: float
    ) -> ComponentResult:
        supply, exhaust = inlets["supply_in"], inlets["exhaust_in"]
        speed = actuators.get("speed", 1.0)
        bypass = actuators.get("bypass", 0.0)
        s_in, e_in, cond_swap = carryover_swap(supply, exhaust, self.cfg.eatr, p)
        x = exchange(
            s_in, e_in, self.cfg.eps_sens * speed, self.cfg.eps_lat * speed, bypass, p
        )
        condensate = x.condensate + cond_swap
        return ComponentResult(
            outlets={"supply_out": x.supply_out, "exhaust_out": x.exhaust_out},
            loads={"condensate": condensate},
            checks=[Check("frost", x.exhaust_t_raw, 0.0, "C", not x.frost)],
            residuals=closure_residuals(
                [supply, exhaust],
                [x.supply_out, x.exhaust_out],
                water_removed=condensate,
            ),
        )
