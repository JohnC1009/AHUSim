"""Chilled-water cooling coil: design mode (ADP / bypass factor) and measured mode.

Design mode (spec §5.4), calibrated from one rating point:
  ADP  = where the rated entering→leaving line, extended, meets saturation.
  BF   = (LAT − ADP) / (EAT − ADP), the same in T and in W (collinear).
  Off-design airflow: BF = BF_rated ^ ((m / m_rated) ^ −0.2), i.e. BF = exp(−NTU)
  with NTU ∝ m^−0.2 (air-side coefficient ∝ velocity^0.8). Assumption to be
  validated in M1-9. ADP is held at its rated value (CHWS = rated CHWS).
  Valve open: leaving = ADP + BF·(entering − ADP) on T and W; sensible only
  (W constant) when the entering dew point is at or below the ADP.
  Valve u < 1: h and W move linearly from entering (u = 0) to valve-open (u = 1).
Condensate leaves with zero enthalpy (same convention as condense_to_saturation),
so q_total = m·(h_in − h_out), the air-side total that coil selections report.

Known limit: with ADP fixed, capacity grows without bound as entering enthalpy
rises. `chwr_implied` = CHWS + Q / C_water (C_water from the rating's energy
balance, rated water flow) makes this visible: a value far above the rated
CHWR means the model is outrunning the water side. See M1-9.
"""

import math

from ahuverify import schema
from ahuverify._numeric import bisect
from ahuverify.components import Check, ComponentResult, at_most, closure_residuals
from ahuverify.psychro import si
from ahuverify.state import AirState, AirStream, condense_to_saturation


def apparatus_dew_point(entering: AirState, leaving: AirState) -> float:
    """ADP (°C): the coil line from entering through leaving, extended to saturation.

    Along the line W(T) = W_L + (T − T_L)·(W_L − W_E)/(T_L − T_E). The ADP is
    the T below T_L where W(T) = W_sat(T) (ASHRAE Fundamentals, coil
    "apparatus dew point" construction).
    """
    if leaving.t_db >= entering.t_db:
        raise ValueError("Coil rating must cool the air: LAT below EAT.")
    slope = (leaving.w - entering.w) / (leaving.t_db - entering.t_db)

    def gap(t: float) -> float:
        return si.GetSatHumRatio(t, leaving.p) - (
            leaving.w + (t - leaving.t_db) * slope
        )

    lo = leaving.t_db
    while gap(lo) > 0:
        lo -= 1.0
        if lo < -50.0:
            raise ValueError("Coil line does not reach saturation above -50 °C.")
    return bisect(gap, lo, leaving.t_db, tol=1e-6)


def bypass_factor_at_airflow(bf_rated: float, m: float, m_rated: float) -> float:
    """BF = BF_rated ^ ((m / m_rated) ^ −0.2)  (spec §5.4, from NTU ∝ m^−0.2)."""
    return bf_rated ** ((m / m_rated) ** -0.2)


def split_sensible_latent(
    m: float, inlet: AirState, outlet: AirState
) -> tuple[float, float]:
    """(sensible, latent) heat removed, W.

    Latent = m·(h_in − h(T_in, W_out)): the moisture change at entering
    temperature; sensible = total − latent (ASHRAE Fundamentals Ch. 1 convention).
    """
    total = m * (inlet.h - outlet.h) * 1000.0
    latent = (
        m * (inlet.h - si.GetMoistAirEnthalpy(inlet.t_db, outlet.w) / 1000.0) * 1000.0
    )
    return total - latent, latent


def _face_velocity_checks(cfg, inlet: AirStream) -> list[Check]:
    if cfg.max_face_velocity is None:
        return []
    v_face = inlet.m_da * inlet.state.v / cfg.face_area.si
    return [at_most("face_velocity", v_face, cfg.max_face_velocity.si, "m/s")]


def _result(
    cfg, inlet: AirStream, out_state: AirState, adp: float, bf: float, extra_checks
) -> ComponentResult:
    m = inlet.m_da
    out = AirStream(out_state, m)
    condensate = m * max(inlet.state.w - out_state.w, 0.0)
    q_total = m * (inlet.state.h - out_state.h) * 1000.0
    q_sens, q_lat = split_sensible_latent(m, inlet.state, out_state)
    return ComponentResult(
        outlets={"out": out},
        loads={
            "q_total": q_total,
            "q_sens": q_sens,
            "q_lat": q_lat,
            "shr": q_sens / q_total if q_total > 0 else 1.0,
            "condensate": condensate,
            "adp": adp,  # °C (diagnostic)
            "bf": bf,  # – (diagnostic)
        },
        checks=_face_velocity_checks(cfg, inlet) + extra_checks,
        residuals=closure_residuals(
            [inlet], [out], water_removed=condensate, heat_added=-q_total
        ),
    )


class CoolingCoilDesignMode:
    type = "cooling_coil_chw"

    def __init__(self, name: str, cfg: schema.CoolingCoilDesign, *, p: float):
        self.name = name
        self.cfg = cfg
        r = cfg.rating
        eat = AirState.from_db_wb(r.eat_db.si, r.eat_wb.si, p)
        lat = AirState.from_db_wb(r.lat_db.si, r.lat_wb.si, p)
        self.t_adp = apparatus_dew_point(eat, lat)
        self.w_adp = si.GetSatHumRatio(self.t_adp, p)
        self.bf_rated = (lat.t_db - self.t_adp) / (eat.t_db - self.t_adp)
        self.m_rated = r.airflow.si / eat.v  # rating airflow at entering conditions
        q_rated = self.m_rated * (eat.h - lat.h)  # kW
        self.chws = r.chws.si
        self.c_water = q_rated / (r.chwr.si - r.chws.si)  # kW/K at rated water flow

    def bypass_factor(self, m: float) -> float:
        return bypass_factor_at_airflow(self.bf_rated, m, self.m_rated)

    def valve_open_leaving(self, inlet: AirStream) -> tuple[float, float]:
        """(T, W) leaving at valve = 1: ADP + BF·(entering − ADP); W kept if coil is dry."""
        s = inlet.state
        bf = self.bypass_factor(inlet.m_da)
        t = self.t_adp + bf * (s.t_db - self.t_adp)
        if s.t_dp <= self.t_adp:
            return t, s.w
        return t, self.w_adp + bf * (s.w - self.w_adp)

    def solve(
        self, inlets: dict[str, AirStream], actuators: dict[str, float], p: float
    ) -> ComponentResult:
        inlet = inlets["in"]
        u = actuators["valve"]
        s = inlet.state
        t_open, w_open = self.valve_open_leaving(inlet)
        h_open = si.GetMoistAirEnthalpy(t_open, w_open) / 1000.0
        h = s.h - u * (s.h - h_open)
        w = s.w - u * (s.w - w_open)
        out_state, _ = condense_to_saturation(h, w, p)  # fog water counts as condensate
        result = _result(
            self.cfg, inlet, out_state, self.t_adp, self.bypass_factor(inlet.m_da), []
        )
        q_kw = result.loads["q_total"] / 1000.0
        result.loads["chwr_implied"] = self.chws + q_kw / self.c_water  # °C
        return result


class CoolingCoilMeasuredMode:
    type = "cooling_coil_chw"

    def __init__(self, name: str, cfg: schema.CoolingCoilMeasured):
        self.name = name
        self.cfg = cfg

    def solve(
        self, inlets: dict[str, AirStream], actuators: dict[str, float], p: float
    ) -> ComponentResult:
        """Force the measured leaving state; back-calculate ADP, BF, loads and SHR.

        Reachable only if neither W nor h rises across the coil. ADP and BF are
        reported as NaN when the coil is dry or does not cool (no coil line).
        """
        inlet = inlets["in"]
        s = inlet.state
        out = AirState.from_db_rh(self.cfg.leaving.db.si, self.cfg.leaving.rh.si, p)
        reachable = out.w <= s.w * (1 + 1e-9) and out.h <= s.h + 1e-9
        adp = bf = math.nan
        if reachable and out.w < s.w and out.t_db < s.t_db:
            adp = apparatus_dew_point(s, out)
            bf = (out.t_db - adp) / (s.t_db - adp)
        check = Check("reachable", out.w, s.w, "kg/kg", reachable)
        return _result(self.cfg, inlet, out, adp, bf, [check])
