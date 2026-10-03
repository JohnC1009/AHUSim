"""Hot-water heating coil, calibrated from one rating point by ε-NTU (spec §5.4).

Used for preheat and reheat. Model:
  1. From the rating: Q = m·(h_LAT − h_EAT); C_air = Q / (LAT − EAT);
     C_water = Q / (EWT − LWT); ε = Q / (C_min·(EWT − EAT)).
  2. Solve NTU from ε with the cross-flow, both-fluids-unmixed correlation;
     UA = NTU·C_min. UA is held constant off-design (assumption).
  3. At valve = 1: Q_max = ε·C_min·(EWT − EAT) with the actual air and the
     rated water capacity rate and EWT. Valve maps linearly to output.
  4. Sensible only: W constant.
Rating air humidity is not given by coil ratings; it is taken as 50 % RH at
EAT (effect on UA under 0.2 %). See docs/decisions/0004.
"""

import math

from ahuverify import schema
from ahuverify._numeric import bisect
from ahuverify.components import ComponentResult, at_most, closure_residuals
from ahuverify.psychro import si
from ahuverify.state import AirState, AirStream

_RATING_RH = 0.5


def crossflow_unmixed_effectiveness(ntu: float, cr: float) -> float:
    """ε for cross-flow with both fluids unmixed.

    ε = 1 − exp[(1/Cr)·NTU^0.22·(exp(−Cr·NTU^0.78) − 1)]
    (Incropera & DeWitt, Fundamentals of Heat and Mass Transfer, Table 11.3;
    the standard approximation for this arrangement). Cr = C_min / C_max.
    """
    if cr < 1e-9:
        return 1.0 - math.exp(-ntu)
    return 1.0 - math.exp((ntu**0.22 / cr) * (math.exp(-cr * ntu**0.78) - 1.0))


def moist_air_capacity_rate(m_da: float, state: AirState) -> float:
    """Air capacity rate, kW/K: m_da × ∂h/∂T at constant W (from PsychroLib)."""
    cp = (
        si.GetMoistAirEnthalpy(state.t_db + 1.0, state.w)
        - si.GetMoistAirEnthalpy(state.t_db, state.w)
    ) / 1000.0
    return m_da * cp


class HeatingCoilHw:
    type = "heating_coil_hw"

    def __init__(self, name: str, cfg: schema.HeatingCoilHw, *, p: float):
        self.name = name
        self.cfg = cfg
        r = cfg.rating
        eat = AirState.from_db_rh(r.eat.si, _RATING_RH, p)
        lat = AirState(r.lat.si, eat.w, p)
        m = r.airflow.si / eat.v
        q = m * (lat.h - eat.h)  # kW
        self.ewt = r.ewt.si
        self.c_water = q / (r.ewt.si - r.lwt.si)  # kW/K
        c_air = q / (r.lat.si - r.eat.si)
        c_min, c_max = sorted((c_air, self.c_water))
        eps = q / (c_min * (r.ewt.si - r.eat.si))
        if not 0.0 < eps < crossflow_unmixed_effectiveness(50.0, c_min / c_max):
            raise ValueError(
                f"{name}: rating gives effectiveness {eps:.3f}, not reachable by a cross-flow coil."
            )
        ntu = bisect(
            lambda n: crossflow_unmixed_effectiveness(n, c_min / c_max) - eps,
            1e-9,
            50.0,
            tol=1e-9,
        )
        self.ua = ntu * c_min  # kW/K

    def max_output(self, inlet: AirStream) -> float:
        """Heat output at valve = 1, kW: ε·C_min·(EWT − EAT) with constant UA."""
        c_air = moist_air_capacity_rate(inlet.m_da, inlet.state)
        c_min, c_max = sorted((c_air, self.c_water))
        eps = crossflow_unmixed_effectiveness(self.ua / c_min, c_min / c_max)
        return max(eps * c_min * (self.ewt - inlet.state.t_db), 0.0)

    def solve(
        self, inlets: dict[str, AirStream], actuators: dict[str, float], p: float
    ) -> ComponentResult:
        inlet = inlets["in"]
        valve = actuators["valve"]
        q = valve * self.max_output(inlet)  # kW
        s = inlet.state
        out = AirStream(AirState.from_h_w(s.h + q / inlet.m_da, s.w, p), inlet.m_da)
        checks = []
        if self.cfg.max_face_velocity is not None:
            v_face = inlet.m_da * s.v / self.cfg.face_area.si
            checks.append(
                at_most("face_velocity", v_face, self.cfg.max_face_velocity.si, "m/s")
            )
        return ComponentResult(
            outlets={"out": out},
            loads={"q_total": q * 1000.0, "q_sens": q * 1000.0},
            checks=checks,
            residuals=closure_residuals([inlet], [out], heat_added=q * 1000.0),
        )
