"""M1-4: fan and filter; fixture F-8 (spec §5.4, §10.2)."""

import pytest

from ahuverify import schema
from ahuverify.components.fan import Fan
from ahuverify.components.filter import Filter
from ahuverify.state import AirState, AirStream

P = 101325.0


def fan(
    dp_in_wc=4.0,
    eta_fan=0.65,
    eta_motor=0.92,
    in_airstream=False,
    design_cfm=10000,
    filter_dp=0.0,
):
    cfg = schema.Fan.model_validate(
        {
            "type": "fan",
            "design_airflow": {"value": design_cfm, "unit": "cfm"},
            "total_static": {"value": dp_in_wc, "unit": "in_wc"},
            "eta_fan": eta_fan,
            "eta_motor": eta_motor,
            "motor_in_airstream": in_airstream,
        }
    )
    return Fan("sf1", cfg, filter_dp=filter_dp)


def test_f8_fan_heat_motor_outside():
    inlet = AirStream(AirState(13.0, 0.009, P), 5.0)
    r = fan().solve({"in": inlet}, {}, P)
    out = r.outlets["out"].state
    assert out.t_db - 13.0 == pytest.approx(1.23, abs=0.02)  # 2.22 °F
    assert out.w == inlet.state.w
    assert all(abs(x) < 1e-3 for x in r.residuals.values())


def test_motor_in_airstream_adds_motor_loss():
    inlet = AirStream(AirState(13.0, 0.009, P), 5.0)
    dt_out = (
        fan(in_airstream=False).solve({"in": inlet}, {}, P).outlets["out"].state.t_db
        - 13
    )
    dt_in = (
        fan(in_airstream=True).solve({"in": inlet}, {}, P).outlets["out"].state.t_db
        - 13
    )
    assert dt_in == pytest.approx(dt_out / 0.92, rel=1e-3)


def test_filter_dp_adds_to_fan_heat():
    inlet = AirStream(AirState(13.0, 0.009, P), 5.0)
    base = fan(dp_in_wc=4.0).solve({"in": inlet}, {}, P).outlets["out"].state.t_db
    with_filter = (
        fan(dp_in_wc=3.0, filter_dp=249.0889)
        .solve({"in": inlet}, {}, P)
        .outlets["out"]
        .state.t_db
    )
    assert with_filter == pytest.approx(base, abs=1e-6)


def test_airflow_above_design_check():
    inlet = AirStream(AirState(13.0, 0.009, P), 5.0)  # ~ 5.0 × 0.82 m³/s ≈ 8,700 cfm
    assert fan(design_cfm=10000).solve({"in": inlet}, {}, P).checks[0].passed
    assert not fan(design_cfm=8000).solve({"in": inlet}, {}, P).checks[0].passed


def test_filter_passes_air_unchanged():
    cfg = schema.Filter.model_validate(
        {
            "type": "filter",
            "dp_clean": {"value": 0.35, "unit": "in_wc"},
            "dp_dirty": {"value": 1.0, "unit": "in_wc"},
        }
    )
    flt = Filter("flt1", cfg)
    inlet = AirStream(AirState(20.0, 0.008, P), 3.0)
    r = flt.solve({"in": inlet}, {}, P)
    assert r.outlets["out"] == inlet
    assert flt.dp == pytest.approx(249.0889)  # dirty ΔP feeds fan heat
