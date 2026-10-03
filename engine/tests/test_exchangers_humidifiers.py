"""M1-7: humidifiers, energy wheel, sensible HX family, desiccant wheel; F-11, F-13."""

import pytest

from ahuverify import schema
from ahuverify.components.adiabatic_humidifier import AdiabaticHumidifier
from ahuverify.components.desiccant_wheel import DesiccantWheel
from ahuverify.components.energy_wheel import EnergyWheel
from ahuverify.components.sensible_hx import SensibleHx
from ahuverify.components.steam_humidifier import SteamHumidifier
from ahuverify.state import AirState, AirStream

P = 101325.0


def closes(result):
    return all(abs(x) < 1e-3 for x in result.residuals.values())


def wheel(eps_s=0.75, eps_l=0.65, eatr=0.0) -> EnergyWheel:
    cfg = schema.EnergyWheel(
        type="energy_wheel", eps_sens=eps_s, eps_lat=eps_l, purge=True, eatr=eatr
    )
    return EnergyWheel("erw1", cfg)


def cross_inlets(oa: AirState, ra: AirState, m_s: float, m_e: float):
    return {"supply_in": AirStream(oa, m_s), "exhaust_in": AirStream(ra, m_e)}


SUMMER_OA = AirState.from_db_rh(35.0, 0.40, P)
SUMMER_RA = AirState.from_db_rh(24.0, 0.50, P)
WINTER_OA = AirState.from_db_rh(-15.0, 0.70, P)
WINTER_RA = AirState.from_db_rh(22.0, 0.30, P)


@pytest.mark.parametrize("ratio", [1.0, 1.07])
def test_f11_wheel_closes_and_uses_mass_ratio(ratio):
    m_e = 4.0
    r = wheel().solve(cross_inlets(SUMMER_OA, SUMMER_RA, ratio * m_e, m_e), {}, P)
    assert closes(r), r.residuals
    s_in, s_out = SUMMER_OA, r.outlets["supply_out"].state
    e_in, e_out = SUMMER_RA, r.outlets["exhaust_out"].state
    # Water picked up by the exhaust = water given up by the supply (mass basis).
    assert m_e * (e_out.w - e_in.w) == pytest.approx(
        ratio * m_e * (s_in.w - s_out.w), rel=1e-6
    )
    assert m_e * (e_out.h - e_in.h) == pytest.approx(
        ratio * m_e * (s_in.h - s_out.h), rel=1e-4
    )


def test_wheel_balanced_follows_spec_formula():
    r = wheel().solve(cross_inlets(SUMMER_OA, SUMMER_RA, 4.0, 4.0), {}, P)
    s = r.outlets["supply_out"].state
    assert s.t_db == pytest.approx(35.0 + 0.75 * (24.0 - 35.0), abs=1e-6)
    assert s.w == pytest.approx(
        SUMMER_OA.w + 0.65 * (SUMMER_RA.w - SUMMER_OA.w), rel=1e-9
    )


def test_wheel_effectiveness_applies_to_smaller_flow():
    # More supply than exhaust: the exhaust side cannot exceed ε (second law).
    r = wheel().solve(cross_inlets(SUMMER_OA, SUMMER_RA, 4.0 * 1.5, 4.0), {}, P)
    e_out = r.outlets["exhaust_out"].state
    assert (e_out.t_db - 24.0) / (35.0 - 24.0) == pytest.approx(0.75, abs=0.01)


def test_wheel_speed_and_bypass():
    full = wheel().solve(cross_inlets(SUMMER_OA, SUMMER_RA, 4.0, 4.0), {}, P)
    half_speed = wheel().solve(
        cross_inlets(SUMMER_OA, SUMMER_RA, 4.0, 4.0), {"speed": 0.5}, P
    )
    bypassed = wheel().solve(
        cross_inlets(SUMMER_OA, SUMMER_RA, 4.0, 4.0), {"bypass": 1.0}, P
    )
    dt_full = 35.0 - full.outlets["supply_out"].state.t_db
    assert 35.0 - half_speed.outlets["supply_out"].state.t_db == pytest.approx(
        0.5 * dt_full, rel=1e-6
    )
    assert bypassed.outlets["supply_out"].state.t_db == pytest.approx(35.0, abs=1e-9)
    assert closes(half_speed) and closes(bypassed)


def test_wheel_eatr_carries_exhaust_air_into_supply():
    clean = wheel().solve(cross_inlets(SUMMER_OA, SUMMER_RA, 4.0, 4.0), {}, P)
    dirty = wheel(eatr=0.05).solve(cross_inlets(SUMMER_OA, SUMMER_RA, 4.0, 4.0), {}, P)
    assert dirty.outlets["supply_out"].m_da == pytest.approx(4.0)  # equal-mass swap
    assert dirty.outlets["supply_out"].state.w > clean.outlets["supply_out"].state.w
    assert closes(dirty)


def frost(result):
    return next(c for c in result.checks if c.name == "frost")


def test_f13_winter_wheel_frost_check():
    # F-13 conditions: OA −15 °C / 70 %, RA 22 °C / 30 %, ε 0.75 / 0.65, no bypass.
    # Computed: exhaust leaves ≈ −5.6 °C at ≈ 93 % RH — below 0 °C but NOT
    # saturated, so the spec §5.4 criterion does not flag frost for this
    # enthalpy wheel. Approved by the owner as computed, 2026-10-03
    # (docs/decisions/0004). The sensible-only case below does frost.
    r = wheel().solve(cross_inlets(WINTER_OA, WINTER_RA, 4.0, 4.0), {}, P)
    e_out = r.outlets["exhaust_out"].state
    assert e_out.t_db == pytest.approx(-5.63, abs=0.05)
    assert frost(r).passed
    assert closes(r)


def test_frost_flagged_when_exhaust_saturates_below_freezing():
    r = wheel(eps_l=0.0).solve(cross_inlets(WINTER_OA, WINTER_RA, 4.0, 4.0), {}, P)
    assert not frost(r).passed
    assert r.loads["condensate"] > 0  # frost mass reported, not dropped
    assert closes(r)


def sensible(kind="plate_hx", eps=0.6) -> SensibleHx:
    return SensibleHx("hx1", schema.SensibleHx(type=kind, eps_sens=eps))


@pytest.mark.parametrize("kind", ["plate_hx", "runaround", "heat_pipe"])
def test_sensible_hx_family(kind):
    r = sensible(kind).solve(cross_inlets(SUMMER_OA, SUMMER_RA, 4.0, 4.0), {}, P)
    s = r.outlets["supply_out"].state
    assert s.w == pytest.approx(SUMMER_OA.w)
    assert s.t_db == pytest.approx(35.0 + 0.6 * (24.0 - 35.0), abs=1e-6)
    assert closes(r)


def test_sensible_hx_frosts_in_winter():
    r = sensible(eps=0.75).solve(cross_inlets(WINTER_OA, WINTER_RA, 4.0, 4.0), {}, P)
    assert not frost(r).passed


def steam(max_lb_h=100.0) -> SteamHumidifier:
    cfg = schema.SteamHumidifier(
        type="steam_humidifier",
        max_rate={"value": max_lb_h, "unit": "lb/h"},
        absorption_distance={"value": 3, "unit": "ft"},
    )
    return SteamHumidifier("hum1", cfg)


def test_steam_humidifier_isothermal_and_rate():
    inlet = AirStream(AirState.from_db_rh(20.0, 0.20, P), 4.0)
    r = steam().solve({"in": inlet}, {"output": 0.5}, P)
    out = r.outlets["out"].state
    assert out.t_db == pytest.approx(20.0, abs=1e-9)
    rate = 0.5 * 100.0 * 0.45359237 / 3600.0
    assert out.w == pytest.approx(inlet.state.w + rate / 4.0, rel=1e-9)
    assert closes(r)


def test_steam_humidifier_capped_at_saturation():
    inlet = AirStream(AirState.from_db_rh(20.0, 0.90, P), 0.5)
    r = steam(max_lb_h=500).solve({"in": inlet}, {"output": 1.0}, P)
    assert r.outlets["out"].state.rh == pytest.approx(1.0, abs=1e-6)
    assert not next(c for c in r.checks if c.name == "saturation").passed


def adiabatic(eff=0.9, max_lb_h=1000.0) -> AdiabaticHumidifier:
    cfg = schema.AdiabaticHumidifier(
        type="adiabatic_humidifier",
        effectiveness=eff,
        max_rate={"value": max_lb_h, "unit": "lb/h"},
    )
    return AdiabaticHumidifier("evap1", cfg)


def test_adiabatic_humidifier_constant_enthalpy_toward_wet_bulb():
    inlet = AirStream(AirState.from_db_rh(35.0, 0.20, P), 4.0)
    r = adiabatic().solve({"in": inlet}, {"output": 1.0}, P)
    out = r.outlets["out"].state
    assert out.h == pytest.approx(inlet.state.h, abs=1e-6)
    expected_t = 35.0 - 0.9 * (35.0 - inlet.state.t_wb)
    assert out.t_db == pytest.approx(expected_t, abs=0.01)
    assert closes(r)


def test_adiabatic_humidifier_rate_limit():
    inlet = AirStream(AirState.from_db_rh(35.0, 0.20, P), 4.0)
    r = adiabatic(max_lb_h=20.0).solve({"in": inlet}, {"output": 1.0}, P)
    added = 4.0 * (r.outlets["out"].state.w - inlet.state.w)
    assert added == pytest.approx(20.0 * 0.45359237 / 3600.0, rel=1e-6)
    assert not next(c for c in r.checks if c.name == "rate").passed


def desiccant(regen_kw=50.0) -> DesiccantWheel:
    cfg = schema.DesiccantWheel(
        type="desiccant_wheel",
        eps_lat=0.5,
        regen_heat={"value": regen_kw, "unit": "kW"},
    )
    return DesiccantWheel("dw1", cfg)


def test_desiccant_dries_and_heats_process_air():
    r = desiccant().solve(
        cross_inlets(SUMMER_OA, SUMMER_RA, 4.0, 4.0), {"output": 1.0}, P
    )
    s = r.outlets["supply_out"].state
    assert s.w == pytest.approx(0.5 * SUMMER_OA.w, rel=1e-9)
    assert s.t_db > SUMMER_OA.t_db
    assert closes(r)


def test_desiccant_no_drying_without_regen_heat():
    r = desiccant(regen_kw=0.0).solve(
        cross_inlets(SUMMER_OA, SUMMER_RA, 4.0, 4.0), {"output": 1.0}, P
    )
    assert r.outlets["supply_out"].state.w == pytest.approx(SUMMER_OA.w)
    assert not next(c for c in r.checks if c.name == "regen_heat").passed


def test_wheel_with_no_supply_flow():
    # OA damper closed (warmup): nothing crosses the supply side of the wheel.
    r = wheel(eatr=0.02).solve(cross_inlets(WINTER_OA, WINTER_RA, 0.0, 4.0), {}, P)
    assert r.outlets["supply_out"].m_da == 0.0
    assert r.outlets["exhaust_out"].state.t_db == pytest.approx(22.0, abs=1e-9)
    assert closes(r)
