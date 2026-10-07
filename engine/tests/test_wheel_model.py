"""Energy wheel: effectiveness vs airflow (option 1), Kays & London speed
correction (option 2), and AHRI 1060 leakage (EATR / OACF)."""

import json
from pathlib import Path

import pytest

from ahuverify import schema, units
from ahuverify.components.energy_wheel import (
    EnergyWheel,
    effectiveness_at_airflow,
    leakage_flows,
    speed_corrected,
    speed_correction,
)
from ahuverify.lanes import compile_unit
from ahuverify.solver import solve
from ahuverify.state import AirState, AirStream

P = 101325.0
SUMMER_OA = AirState.from_db_rh(35.0, 0.40, P)
SUMMER_RA = AirState.from_db_rh(24.0, 0.50, P)
CFM = units.to_si(1.0, "cfm")


def closes(r):
    return all(abs(x) < 1e-3 for x in r.residuals.values())


def wheel(**kw) -> EnergyWheel:
    base = {
        "type": "energy_wheel",
        "eps_sens": 0.75,
        "eps_lat": 0.65,
        "purge": True,
        "eatr": 0.0,
    }
    return EnergyWheel("erw1", schema.EnergyWheel.model_validate(base | kw))


def inlets(m_s=4.0, m_e=4.0, oa=SUMMER_OA, ra=SUMMER_RA):
    return {"supply_in": AirStream(oa, m_s), "exhaust_in": AirStream(ra, m_e)}


# ---------- option 1: effectiveness vs airflow ----------

POINTS = [
    (1.0, 0.75, 0.65),
    (0.75, 0.80, 0.72),
]  # (airflow, ε_s, ε_L): AHRI 100 % and 75 %


def test_airflow_interpolation_between_ratings():
    assert effectiveness_at_airflow(POINTS, 1.0) == pytest.approx((0.75, 0.65))
    assert effectiveness_at_airflow(POINTS, 0.75) == pytest.approx((0.80, 0.72))
    assert effectiveness_at_airflow(POINTS, 0.875) == pytest.approx((0.775, 0.685))


def test_airflow_extrapolates_linearly_then_clamps():
    # 125 % airflow: one more step down the same line (as EnergyPlus does).
    assert effectiveness_at_airflow(POINTS, 1.25) == pytest.approx((0.70, 0.58))
    es, el = effectiveness_at_airflow(POINTS, 10.0)
    assert es == 0.0 and el == 0.0
    assert effectiveness_at_airflow([(1.0, 0.75, 0.65)], 0.3) == pytest.approx(
        (0.75, 0.65)
    )


def test_wheel_uses_airflow_ratings():
    # Rated at 10,000 cfm; run at ~75 % of that -> the 75 % effectiveness.
    w = wheel(
        rated_airflow={"value": 10000, "unit": "cfm"},
        airflow_ratings=[
            {
                "airflow": {"value": 7500, "unit": "cfm"},
                "eps_sens": 0.80,
                "eps_lat": 0.72,
            }
        ],
    )
    m = 7500 * CFM / ((SUMMER_OA.v + SUMMER_RA.v) / 2)  # average face flow = 7,500 cfm
    r = w.solve(inlets(m, m), {}, P)
    assert r.loads["eps_sens"] == pytest.approx(0.80, abs=1e-6)
    assert r.loads["eps_lat"] == pytest.approx(0.72, abs=1e-6)
    s = r.outlets["supply_out"].state
    assert s.t_db == pytest.approx(35.0 + 0.80 * (24.0 - 35.0), abs=1e-6)
    assert closes(r)


def test_constant_effectiveness_without_rated_airflow():
    r = wheel().solve(inlets(1.0, 1.0), {}, P)
    assert r.loads["eps_sens"] == 0.75 and r.loads["eps_lat"] == 0.65


# ---------- option 2: speed correction ----------


def test_kays_london_correction_values():
    # 1 − 1/(9·Cr*^1.93), Kays & London
    assert speed_correction(1.0) == pytest.approx(1 - 1 / 9)
    assert speed_correction(10.0) == pytest.approx(1 - 1 / (9 * 10**1.93))
    assert (
        speed_correction(0.2) == 0.0
    )  # formula goes negative below Cr* ≈ 0.32: no transfer
    assert speed_correction(0.0) == 0.0


def test_speed_corrected_relative_to_rated():
    # Rated Cr* = 10. Half speed barely changes ε; 10 % speed costs ~11 %.
    assert speed_corrected(0.75, 10.0, 1.0) == pytest.approx(0.75)
    assert speed_corrected(0.75, 10.0, 0.5) == pytest.approx(
        0.75 * speed_correction(5.0) / speed_correction(10.0)
    )
    assert speed_corrected(0.75, 10.0, 0.1) == pytest.approx(
        0.75 * (8 / 9) / speed_correction(10.0)
    )
    # Latent falls faster: exponent 2 squares the ratio.
    ratio = speed_correction(1.0) / speed_correction(10.0)
    assert speed_corrected(0.65, 10.0, 0.1, exponent=2.0) == pytest.approx(
        0.65 * ratio**2
    )
    assert speed_corrected(0.75, 10.0, 0.0) == 0.0


def matrix_wheel(**kw):
    return wheel(
        rated_speed_rpm=20,
        matrix_heat_capacity={"value": 150, "unit": "Btu/F"},
        **kw,
    )


def test_wheel_speed_model_at_full_and_low_speed():
    full = matrix_wheel().solve(inlets(), {"speed": 1.0}, P)
    plain = wheel().solve(inlets(), {}, P)
    assert full.outlets["supply_out"].state.t_db == pytest.approx(
        plain.outlets["supply_out"].state.t_db
    )
    slow = matrix_wheel(latent_speed_exponent=2.0).solve(inlets(), {"speed": 0.05}, P)
    assert 0 < slow.loads["eps_sens"] < 0.75
    assert (
        slow.loads["eps_lat"] / 0.65 < slow.loads["eps_sens"] / 0.75
    )  # latent falls faster
    assert closes(slow)


def test_without_matrix_data_speed_scales_linearly():
    r = wheel().solve(inlets(), {"speed": 0.5}, P)
    assert r.loads["eps_sens"] == pytest.approx(0.375)


def test_speed_inputs_come_as_a_pair():
    with pytest.raises(ValueError, match="rated_speed_rpm"):
        wheel(rated_speed_rpm=20)


# ---------- leakage: EATR and OACF (AHRI 1060) ----------


def test_leakage_flows_semco_example():
    # SEMCO selection: 32,919 cfm OA in, 30,000 cfm supply out, 2,919 cfm purge/seals.
    oacf = 32919 / 30000
    m_out, m_carry, m_purge = leakage_flows(32919.0, oacf, 0.0)
    assert m_out == pytest.approx(30000.0)
    assert m_carry == 0.0 and m_purge == pytest.approx(2919.0)
    m_out, m_carry, m_purge = leakage_flows(32919.0, oacf, 0.01)
    assert m_carry == pytest.approx(300.0) and m_purge == pytest.approx(3219.0)


def test_wheel_leakage_mass_balance():
    w = wheel(eatr=0.02, oacf=1.10)
    r = w.solve(inlets(4.4, 4.0), {}, P)
    s_out, e_out = r.outlets["supply_out"], r.outlets["exhaust_out"]
    assert s_out.m_da == pytest.approx(4.0)  # 4.4 / 1.10
    # exhaust gains the purge (0.12·4.0) and loses the carryover (0.02·4.0)
    assert e_out.m_da == pytest.approx(4.0 + 0.48 - 0.08)
    assert r.loads["m_purge"] == pytest.approx(0.48) and r.loads[
        "m_carryover"
    ] == pytest.approx(0.08)
    assert closes(r)


def test_carryover_pulls_supply_toward_exhaust_state():
    # Carryover mixes return air into the supply: in summer the RA (9.3 g/kg)
    # is drier than the wheel's supply leaving (~11 g/kg), so supply gets drier.
    clean = wheel().solve(inlets(), {}, P).outlets["supply_out"].state
    dirty = wheel(eatr=0.05).solve(inlets(), {}, P).outlets["supply_out"].state
    assert SUMMER_RA.w < dirty.w < clean.w
    assert SUMMER_RA.t_db < dirty.t_db < clean.t_db


def test_oacf_cannot_imply_negative_purge():
    with pytest.raises(ValueError, match="OACF"):
        wheel(eatr=0.0, oacf=0.95)


# ---------- condensation inside the wheel ----------


def test_condensation_flagged_above_freezing():
    humid = AirState.from_db_rh(35.0, 0.80, P)
    cool = AirState.from_db_rh(20.0, 0.50, P)
    r = wheel(eps_lat=0.0).solve(inlets(oa=humid, ra=cool), {}, P)
    check = next(c for c in r.checks if c.name == "condensation")
    assert not check.passed and r.loads["condensate"] > 0
    ok = wheel().solve(inlets(), {}, P)
    assert next(c for c in ok.checks if c.name == "condensation").passed


# ---------- in the unit ----------


def test_solver_draws_extra_oa_through_a_leaky_wheel():
    data = json.loads(
        (Path(__file__).parent / "fixtures" / "example_6_1.json").read_text()
    )
    data["components"]["erw1"]["oacf"] = 1.10
    unit = compile_unit(schema.UnitConfig.model_validate(data))
    oa = AirState.from_db_wb(units.to_si(91, "F"), units.to_si(74, "F"), unit.p)
    ra = AirState.from_db_rh(units.to_si(75, "F"), 0.5, unit.p)
    r = solve(
        unit,
        oa,
        ra,
        {
            "mix1.oa_fraction": 0.3,
            "cc1.valve": 1.0,
            "phc1.valve": 0.0,
            "rhc1.valve": 0.0,
        },
    )
    assert r.converged and r.valid, r.failures
    m_oa_at_damper = r.components["mix1"].loads["m_oa"]
    assert r.states["oa_intake"].m_da == pytest.approx(1.10 * m_oa_at_damper, rel=1e-5)
    # whole-unit dry-air balance still closes
    m_in = r.states["oa_intake"].m_da + r.states["ra"].m_da
    m_out = r.states["after:sf1"].m_da + r.states["after:ef1"].m_da
    assert m_out == pytest.approx(m_in, rel=1e-6)
