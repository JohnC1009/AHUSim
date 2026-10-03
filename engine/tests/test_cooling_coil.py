"""M1-6: chilled-water cooling coil, design and measured modes; F-9."""

import json
from pathlib import Path

import pytest

from ahuverify import schema, units
from ahuverify.components.cooling_coil import (
    CoolingCoilDesignMode,
    CoolingCoilMeasuredMode,
    apparatus_dew_point,
)
from ahuverify.psychro import si
from ahuverify.state import AirState, AirStream

P = 101325.0
FIXTURE = Path(__file__).parent / "fixtures" / "example_6_1.json"


def F(t_f: float) -> float:
    return units.to_si(t_f, "F")


def cc1() -> CoolingCoilDesignMode:
    cfg = schema.UnitConfig.model_validate(json.loads(FIXTURE.read_text())).components[
        "cc1"
    ]
    return CoolingCoilDesignMode("cc1", cfg, p=P)


def rated_inlet(t_db_f=80.5, t_wb_f=67.0, cfm=10000.0) -> AirStream:
    rated = AirState.from_db_wb(F(80.5), F(67.0), P)
    m = units.to_si(cfm, "cfm") / rated.v
    return AirStream(AirState.from_db_wb(F(t_db_f), F(t_wb_f), P), m)


def test_adp_lies_on_saturation_and_on_the_coil_line():
    e = AirState.from_db_wb(F(80.5), F(67.0), P)
    lv = AirState.from_db_wb(F(55.0), F(54.0), P)
    t_adp = apparatus_dew_point(e, lv)
    w_adp = si.GetSatHumRatio(t_adp, P)
    # Collinear: same fraction along the line in T and in W.
    assert (lv.t_db - t_adp) / (e.t_db - t_adp) == pytest.approx(
        (lv.w - w_adp) / (e.w - w_adp), rel=1e-4
    )
    assert t_adp < lv.t_dp


def test_f9_reproduces_rating():
    r = cc1().solve({"in": rated_inlet()}, {"valve": 1.0}, P)
    out = r.outlets["out"].state
    assert out.t_db == pytest.approx(F(55.0), abs=0.1)
    assert out.t_wb == pytest.approx(F(54.0), abs=0.1)
    assert all(abs(x) < 1e-3 for x in r.residuals.values()), r.residuals
    assert r.loads["condensate"] > 0
    assert 0 < r.loads["shr"] < 1


def test_bypass_factor_grows_with_airflow():
    c = cc1()
    bf_rated = c.bypass_factor(rated_inlet().m_da)
    assert c.bypass_factor(rated_inlet(cfm=12000).m_da) > bf_rated
    assert c.bypass_factor(rated_inlet(cfm=8000).m_da) < bf_rated
    # BF = BF_r ^ ((m/m_r)^-0.2)
    assert c.bypass_factor(rated_inlet(cfm=12000).m_da) == pytest.approx(
        bf_rated ** (1.2**-0.2), rel=1e-6
    )


def test_dry_coil_when_dew_point_below_adp():
    inlet = AirStream(AirState.from_db_rh(F(75.0), 0.20, P), rated_inlet().m_da)
    r = cc1().solve({"in": inlet}, {"valve": 1.0}, P)
    assert r.outlets["out"].state.w == pytest.approx(inlet.state.w)
    assert r.loads["condensate"] == 0.0
    assert r.loads["shr"] == pytest.approx(1.0)


def test_valve_interpolates_enthalpy_linearly():
    c = cc1()
    inlet = rated_inlet()
    full = c.solve({"in": inlet}, {"valve": 1.0}, P)
    half = c.solve({"in": inlet}, {"valve": 0.5}, P)
    off = c.solve({"in": inlet}, {"valve": 0.0}, P)
    assert half.loads["q_total"] == pytest.approx(0.5 * full.loads["q_total"], rel=1e-6)
    assert off.outlets["out"].state.t_db == pytest.approx(inlet.state.t_db, abs=1e-9)


def test_face_velocity_check_500_fpm():
    r = cc1().solve({"in": rated_inlet()}, {"valve": 1.0}, P)
    fv = next(c for c in r.checks if c.name == "face_velocity")
    assert units.from_si(fv.value, "fpm") == pytest.approx(10000 / 22, rel=1e-6)
    assert fv.passed


def measured(db_f: float, rh_pct: float) -> CoolingCoilMeasuredMode:
    cfg = schema.CoolingCoilMeasured.model_validate(
        {
            "type": "cooling_coil_chw",
            "mode": "measured",
            "face_area": {"value": 22, "unit": "ft2"},
            "leaving": {
                "db": {"value": db_f, "unit": "F"},
                "rh": {"value": rh_pct, "unit": "%"},
            },
        }
    )
    return CoolingCoilMeasuredMode("cc1", cfg)


def test_measured_mode_back_calculates_adp_bf():
    lv = AirState.from_db_wb(F(55.0), F(54.0), P)
    r = measured(55.0, lv.rh * 100).solve({"in": rated_inlet()}, {}, P)
    design = cc1().solve({"in": rated_inlet()}, {"valve": 1.0}, P)
    assert r.loads["adp"] == pytest.approx(design.loads["adp"], abs=0.05)
    assert r.loads["bf"] == pytest.approx(design.loads["bf"], abs=0.01)
    assert next(c for c in r.checks if c.name == "reachable").passed
    assert all(abs(x) < 1e-3 for x in r.residuals.values())


def test_measured_mode_flags_unreachable_state():
    # Leaving wetter than entering: no cooling coil does that.
    r = measured(75.0, 90.0).solve({"in": rated_inlet()}, {}, P)
    assert not next(c for c in r.checks if c.name == "reachable").passed


def test_implied_chwr_reproduces_rating_and_rises_with_load():
    c = cc1()
    rated = c.solve({"in": rated_inlet()}, {"valve": 1.0}, P).loads["chwr_implied"]
    assert rated == pytest.approx(F(56.0), abs=0.05)
    hot = c.solve({"in": rated_inlet(95, 78)}, {"valve": 1.0}, P).loads["chwr_implied"]
    assert hot > rated


def test_adp_shifts_with_chws():
    # Spec §5.4: ADP moves by (CHWS − CHWS_rated); colder water, colder leaving air.
    c = cc1()
    t_rated, _ = c.valve_open_leaving(rated_inlet())
    t_cold, _ = c.valve_open_leaving(rated_inlet(), chws=F(42.0))
    assert c.adp_at(F(42.0)) == pytest.approx(c.t_adp - 2.0 / 1.8, abs=1e-9)
    assert t_cold < t_rated
