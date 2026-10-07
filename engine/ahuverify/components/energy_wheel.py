"""Energy (enthalpy) wheel: sensible and latent recovery between lanes (spec §5.4).

Effectiveness model (EnergyPlus HeatExchanger:AirToAir:SensibleAndLatent, AHRI 1060):
  supply leaving = OA + ε·(m_min / m_supply)·(RA − OA), on T with ε_s and on W
  with ε_L (see _exchange.py), exhaust side by energy and water balance.
ε comes from three optional refinements, each off unless its inputs are given:
  1. Airflow: ε_s, ε_L at rated_airflow plus extra airflow_ratings, linearly
     interpolated on the average face airflow (extrapolated on the nearest
     segment beyond them, clamped to 0–1).
  2. Speed: Kays & London rotary-regenerator correction, relative to rated
     speed, from rated_speed_rpm and matrix_heat_capacity. Latent is raised to
     latent_speed_exponent (≥ 1) because the desiccant saturates sooner at low
     rpm — a calibration knob, fit it to selections at 2–3 speeds. Without the
     two inputs, speed scales ε linearly (docs/decisions/0004).
  3. Leakage (AHRI 1060): EATR and OACF set the carryover (exhaust → supply)
     and purge/seal (OA → exhaust) flows; that air bypasses the exchange.
Actuators: `bypass` (0–1, default 0) and `speed` (0–1 of rated, default 1).
"""

from ahuverify import schema
from ahuverify.components import Check, ComponentResult, at_most, closure_residuals
from ahuverify.components._exchange import exchange
from ahuverify.components.heating_coil import moist_air_capacity_rate
from ahuverify.components.mixing_box import mix_airstreams
from ahuverify.state import AirStream


def effectiveness_at_airflow(
    points: list[tuple[float, float, float]], airflow: float
) -> tuple[float, float]:
    """(ε_s, ε_L) at `airflow` from rating points (airflow, ε_s, ε_L).

    Piecewise-linear interpolation; beyond the outermost points the nearest
    segment is extended (as EnergyPlus extrapolates its 75 % / 100 % ratings).
    One point means constant ε. Results are clamped to 0–1.
    """
    pts = sorted(points)
    if len(pts) == 1:
        return pts[0][1], pts[0][2]
    i = 0
    while i < len(pts) - 2 and airflow > pts[i + 1][0]:
        i += 1
    (q0, s0, l0), (q1, s1, l1) = pts[i], pts[i + 1]
    f = (airflow - q0) / (q1 - q0)
    return _fraction(s0 + f * (s1 - s0)), _fraction(l0 + f * (l1 - l0))


def _fraction(e: float) -> float:
    return min(max(e, 0.0), 1.0)


def speed_correction(cr_star: float) -> float:
    """Kays & London rotary-regenerator factor: 1 − 1 / (9·Cr*^1.93).

    Cr* = matrix heat capacity rate / C_min = (M·c·rpm/60) / C_min. The
    correlation is for Cr* above ~0.4; below Cr* ≈ 0.32 it would go negative,
    so it is clamped to 0 (wheel too slow to carry heat).
    (Kays & London, Compact Heat Exchangers; Lambertson 1958.)
    """
    if cr_star <= 0.0:
        return 0.0
    return max(1.0 - 1.0 / (9.0 * cr_star**1.93), 0.0)


def speed_corrected(
    eps_rated: float, cr_star_rated: float, speed: float, exponent: float = 1.0
) -> float:
    """ε at a fraction of rated speed: ε_rated · [f(Cr*·speed) / f(Cr*_rated)]^exponent."""
    ratio = speed_correction(cr_star_rated * speed) / speed_correction(cr_star_rated)
    return eps_rated * ratio**exponent


def leakage_flows(
    m_oa_in: float, oacf: float, eatr: float
) -> tuple[float, float, float]:
    """(supply out, carryover, purge) dry-air flows from the OA drawn into the wheel.

    AHRI 1060: OACF = OA in / supply out; EATR = share of supply out that came
    from the exhaust. Supply out = OA in / OACF; carryover = EATR·supply out;
    purge (OA lost to the exhaust) = OA in − supply out + carryover
    = (OACF − 1 + EATR)·supply out.
    """
    m_out = m_oa_in / oacf
    m_carry = eatr * m_out
    return m_out, m_carry, m_oa_in - m_out + m_carry


class EnergyWheel:
    type = "energy_wheel"

    def __init__(self, name: str, cfg: schema.EnergyWheel):
        self.name = name
        self.cfg = cfg
        self.oacf = cfg.oacf
        pts = (
            [(cfg.rated_airflow.si, cfg.eps_sens, cfg.eps_lat)]
            if cfg.rated_airflow
            else []
        )
        pts += [(r.airflow.si, r.eps_sens, r.eps_lat) for r in cfg.airflow_ratings]
        self.ratings = pts or [(1.0, cfg.eps_sens, cfg.eps_lat)]

    def effectiveness(
        self, supply: AirStream, exhaust: AirStream, speed: float
    ) -> tuple[float, float]:
        """(ε_s, ε_L) for these exchanged flows at this speed fraction."""
        face = 0.5 * (
            supply.m_da * supply.state.v + exhaust.m_da * exhaust.state.v
        )  # m³/s
        es, el = effectiveness_at_airflow(self.ratings, face)
        c = self.cfg
        if c.matrix_heat_capacity is None:
            return es * speed, el * speed
        c_min = min(
            moist_air_capacity_rate(supply.m_da, supply.state),
            moist_air_capacity_rate(exhaust.m_da, exhaust.state),
        )
        if c_min <= 0.0:
            return es, el
        cr_rated = c.matrix_heat_capacity.si * (c.rated_speed_rpm / 60.0) / c_min
        return speed_corrected(es, cr_rated, speed), speed_corrected(
            el, cr_rated, speed, c.latent_speed_exponent
        )

    def solve(
        self, inlets: dict[str, AirStream], actuators: dict[str, float], p: float
    ) -> ComponentResult:
        supply, exhaust = inlets["supply_in"], inlets["exhaust_in"]
        speed = actuators.get("speed", 1.0)
        bypass = actuators.get("bypass", 0.0)
        _, m_carry, m_purge = leakage_flows(supply.m_da, self.oacf, self.cfg.eatr)
        if m_carry > exhaust.m_da:
            raise ValueError(
                f"{self.name}: carryover ({m_carry:.3f} kg/s) exceeds the exhaust airflow."
            )
        through_s = AirStream(
            supply.state, supply.m_da - m_purge
        )  # OA crossing the matrix
        through_e = AirStream(exhaust.state, exhaust.m_da - m_carry)
        eps_s, eps_l = self.effectiveness(through_s, through_e, speed)
        x = exchange(through_s, through_e, eps_s, eps_l, bypass, p)
        supply_out, c1 = mix_airstreams(
            [x.supply_out, AirStream(exhaust.state, m_carry)], p
        )
        exhaust_out, c2 = mix_airstreams(
            [x.exhaust_out, AirStream(supply.state, m_purge)], p
        )
        condensate = x.condensate + c1 + c2
        return ComponentResult(
            outlets={"supply_out": supply_out, "exhaust_out": exhaust_out},
            loads={
                "condensate": condensate,
                "m_carryover": m_carry,
                "m_purge": m_purge,
                "eps_sens": eps_s,
                "eps_lat": eps_l,
            },
            checks=[
                Check("frost", x.exhaust_t_raw, 0.0, "C", not x.frost),
                at_most("condensation", x.max_rh_above_freezing, 1.0, "-"),
            ],
            residuals=closure_residuals(
                [supply, exhaust], [supply_out, exhaust_out], water_removed=condensate
            ),
        )
