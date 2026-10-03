"""M1-2: AirState and constructors; fixtures F-1 … F-6 (spec §5.1, §10.1)."""

import pytest

from ahuverify.psychro import si
from ahuverify.state import AirState, condense_to_saturation

P = 101325.0

# id, t_db °C, RH, W g/kg, h kJ/kg, v m³/kg, T_dp °C, T_wb °C
PROPERTY_FIXTURES = [
    ("F-1", 25.0, 0.50, 9.881, 50.322, 0.8580, 13.86, 17.89),
    ("F-2", 35.0, 0.40, 14.132, 71.473, 0.8928, 19.38, 23.93),
    ("F-3", 24.0, 0.50, 9.299, 47.815, 0.8544, 12.95, 17.07),
]


@pytest.mark.parametrize("fid, t, rh, w_g, h, v, t_dp, t_wb", PROPERTY_FIXTURES)
def test_property_fixtures(fid, t, rh, w_g, h, v, t_dp, t_wb):
    s = AirState.from_db_rh(t, rh, P)
    assert s.w * 1000 == pytest.approx(w_g, rel=1e-3)
    assert s.h == pytest.approx(h, rel=1e-3)
    assert s.v == pytest.approx(v, rel=1e-3)
    assert s.t_dp == pytest.approx(t_dp, abs=0.05)
    assert s.t_wb == pytest.approx(t_wb, abs=0.05)
    assert s.rh == pytest.approx(rh, abs=1e-9)


def test_f4_saturation_pressure():
    assert si.GetSatVapPres(25.0) == pytest.approx(3169.2, abs=0.05)
    assert si.GetSatVapPres(0.0) == pytest.approx(611.2, abs=0.05)


def test_f5_ip_display():
    from ahuverify import units

    s = AirState.from_db_rh(units.to_si(70.0, "F"), 0.50, P)
    assert s.w * 7000 == pytest.approx(54.48, abs=0.01)  # gr/lb
    assert units.enthalpy_ip(s.t_db, s.w) == pytest.approx(25.30, abs=0.01)
    assert units.enthalpy_ip(s.t_db, s.w) != pytest.approx(s.h / 2.326, abs=1.0)


def test_f6_ice_bulb_branch():
    s = AirState.from_db_rh(-10.0, 0.80, P)
    assert s.t_wb == pytest.approx(-10.65, abs=0.05)


def test_constructors_agree():
    ref = AirState.from_db_rh(25.0, 0.5, P)
    for other in (
        AirState.from_db_w(25.0, ref.w, P),
        AirState.from_db_wb(25.0, ref.t_wb, P),
        AirState.from_db_dp(25.0, ref.t_dp, P),
        AirState.from_h_w(ref.h, ref.w, P),
    ):
        assert other.t_db == pytest.approx(ref.t_db, abs=0.01)
        assert other.w == pytest.approx(ref.w, rel=1e-3)


def test_supersaturated_request_is_refused():
    w_sat = si.GetSatHumRatio(20.0, P)
    with pytest.raises(ValueError, match="supersaturated"):
        AirState.from_db_w(20.0, w_sat * 1.05, P)
    with pytest.raises(ValueError):
        AirState.from_db_rh(20.0, 1.2, P)


def test_condense_to_saturation_keeps_enthalpy():
    # Foggy mix: 2 °C with more water than saturation allows.
    h_in = si.GetMoistAirEnthalpy(2.0, 0.006) / 1000
    state, condensate = condense_to_saturation(h_in, 0.006, P)
    assert condensate > 0
    assert state.rh == pytest.approx(1.0, abs=1e-3)
    assert state.h == pytest.approx(h_in, abs=1e-3)  # adiabatic: energy kept
    assert state.w + condensate == pytest.approx(0.006, rel=1e-9)  # water kept


def test_condense_to_saturation_passes_unsaturated_air():
    s = AirState.from_db_rh(25.0, 0.5, P)
    state, condensate = condense_to_saturation(s.h, s.w, P)
    assert condensate == 0.0
    assert state.t_db == pytest.approx(25.0, abs=1e-6)
