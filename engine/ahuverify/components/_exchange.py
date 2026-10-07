"""Air-to-air exchange shared by the energy wheel and the sensible HX family.

Supply side (spec §5.4):  T_s,out = T_s + ε_s·k·(T_e − T_s),  W likewise with ε_l,
where k = m_min / m_wheeled. With m_supply ≤ m_exhaust, k = 1 and this is the
spec formula exactly. When supply exceeds exhaust, ε applies to the smaller
flow (AHRI 1060 definition), so the exhaust side can never exceed ε — the spec
formula alone would let it pass 100 % (second-law violation) at large ratios.
Exhaust side by energy and water balance on dry-air mass:
  h_e,out = h_e − (m_w / m_e)·(h_s,out − h_s),  W_e,out = W_e − (m_w / m_e)·(W_s,out − W_s).
Bypass b blends unexchanged supply air back in by mass (m_w = (1 − b)·m_s).
"""

from dataclasses import dataclass

from ahuverify.components.mixing_box import mix_airstreams
from ahuverify.psychro import si
from ahuverify.state import AirStream, condense_to_saturation


@dataclass
class Exchange:
    supply_out: AirStream
    exhaust_out: AirStream
    condensate: float  # kg/s (both sides; frost on the exhaust side below 0 °C)
    exhaust_t_raw: float  # °C, exhaust leaving before any condensation
    frost: bool  # exhaust leaving below 0 °C and beyond saturation (spec §5.4)
    # Highest leaving RH (before any condensing, 0–1+) of the sides at or above
    # 0 °C; above 1 means water condenses in the exchanger.
    max_rh_above_freezing: float = 0.0


def exhaust_would_frost(t: float, w: float, p: float) -> bool:
    """Frost: exhaust leaving T < 0 °C and W above saturation at that T (spec §5.4)."""
    return t < 0.0 and w > si.GetSatHumRatio(t, p)


def exchange(
    supply: AirStream,
    exhaust: AirStream,
    eps_s: float,
    eps_l: float,
    bypass: float,
    p: float,
) -> Exchange:
    m_s, m_e = supply.m_da, exhaust.m_da
    m_w = (1.0 - bypass) * m_s
    s, e = supply.state, exhaust.state
    if m_w <= 0.0 or m_e <= 0.0:
        return Exchange(supply, exhaust, 0.0, e.t_db, False)
    k = min(m_w, m_e) / m_w
    t_sw = s.t_db + eps_s * k * (e.t_db - s.t_db)
    w_sw = s.w + eps_l * k * (e.w - s.w)
    h_sw = si.GetMoistAirEnthalpy(t_sw, w_sw) / 1000.0
    h_eo = e.h - (m_w / m_e) * (h_sw - s.h)
    w_eo = e.w - (m_w / m_e) * (w_sw - s.w)
    t_eo = si.GetTDryBulbFromEnthalpyAndHumRatio(h_eo * 1000.0, w_eo)

    sw_state, cond_s = condense_to_saturation(h_sw, w_sw, p)
    eo_state, cond_e = condense_to_saturation(h_eo, w_eo, p)
    parts = [AirStream(sw_state, m_w)]
    if bypass > 0.0:
        parts.append(AirStream(s, bypass * m_s))
    supply_out, cond_mix = mix_airstreams(parts, p)
    rh_raw = [
        w / si.GetSatHumRatio(t, p) for t, w in ((t_sw, w_sw), (t_eo, w_eo)) if t >= 0.0
    ]
    return Exchange(
        supply_out=supply_out,
        exhaust_out=AirStream(eo_state, m_e),
        condensate=cond_s * m_w + cond_e * m_e + cond_mix,
        exhaust_t_raw=t_eo,
        frost=exhaust_would_frost(t_eo, w_eo, p),
        max_rh_above_freezing=max(rh_raw, default=0.0),
    )
