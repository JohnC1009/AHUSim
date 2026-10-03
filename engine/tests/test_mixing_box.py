"""M1-3: mixing box on a dry-air mass basis; fixture F-7 (spec §5.4, §10.2)."""

import pytest

from ahuverify import schema
from ahuverify.components.mixing_box import MixingBox, oa_mass_fraction
from ahuverify.state import AirState, AirStream

P = 101325.0
OA = AirState.from_db_rh(35.0, 0.40, P)  # F-2
RA = AirState.from_db_rh(24.0, 0.50, P)  # F-3
CFM = 0.3048**3 / 60  # m³/s per cfm


def box(min_oa_cfm=0.0, freeze_f=None) -> MixingBox:
    damper = {
        "free_area": {"value": 8.0, "unit": "ft2"},
        "max_velocity": {"value": 1500, "unit": "fpm"},
    }
    cfg = schema.MixingBox.model_validate(
        {
            "type": "mixing_box",
            "dampers": {
                "oa": damper,
                "ra": {**damper, "free_area": {"value": 4.5, "unit": "ft2"}},
                "relief": damper,
            },
            **(
                {"freeze_threshold": {"value": freeze_f, "unit": "F"}}
                if freeze_f is not None
                else {}
            ),
        }
    )
    return MixingBox("mix1", cfg, min_oa_flow=min_oa_cfm * CFM)


def run(b, f, m_s=5.0, m_r=4.9):
    inlets = {"oa": AirStream(OA, 0.0), "ra": AirStream(RA, m_r)}
    return b.solve(inlets, {"oa_fraction": f}, P, m_supply=m_s, m_return=m_r)


def test_f7_mass_basis_mix():
    assert oa_mass_fraction(0.30, OA.v, RA.v) == pytest.approx(0.2908, abs=1e-4)
    mixed = run(box(), 0.30).outlets["mixed"].state
    assert mixed.t_db == pytest.approx(27.22, abs=0.05)
    assert mixed.w * 1000 == pytest.approx(10.704, rel=1e-3)
    # A volumetric mix would give 27.30 °C / 10.748 g/kg — must not.
    assert mixed.t_db != pytest.approx(27.30, abs=0.02)


def test_residuals_close():
    for f in (0.0, 0.3, 1.0):
        res = run(box(), f).residuals
        assert all(abs(r) < 1e-3 for r in res.values()), res


def test_flows_split_and_relief():
    r = run(box(), 0.30, m_s=5.0, m_r=4.9)
    m_oa = r.loads["m_oa"]
    assert r.outlets["mixed"].m_da == pytest.approx(5.0)
    assert r.outlets["relief"].m_da == pytest.approx(4.9 - (5.0 - m_oa))
    assert r.outlets["relief"].state == RA


def test_bias_lost_when_oa_below_bias():
    # OA closed: recirculation must carry all 5.0 kg/s, return rises from 4.9.
    r = run(box(), 0.0, m_s=5.0, m_r=4.9)
    assert r.outlets["relief"].m_da == 0.0
    assert r.loads["m_ra"] == pytest.approx(5.0)
    check = next(c for c in r.checks if c.name == "pressurization_bias")
    assert not check.passed


def test_damper_face_velocity_check():
    # All 5.0 kg/s through the 4.5 ft² return damper.
    r = run(box(), 0.0, m_s=5.0, m_r=5.0)
    ra = next(c for c in r.checks if c.name == "face_velocity_ra")
    expected = 5.0 * RA.v / (4.5 * 0.3048**2)
    assert ra.value == pytest.approx(expected)
    assert ra.limit == pytest.approx(1500 * 0.3048 / 60)
    assert not ra.passed


def test_min_oa_check():
    # 30 % of 5.0 kg/s is ~1.3 m³/s (~2,750 cfm) of OA.
    r = run(box(min_oa_cfm=2000), 0.30)
    assert next(c for c in r.checks if c.name == "min_oa").passed
    r = run(box(min_oa_cfm=3000), 0.30)
    assert not next(c for c in r.checks if c.name == "min_oa").passed


def test_freeze_check_both_sides():
    # Mixed air is 27.22 °C = 81.0 °F.
    r = run(box(freeze_f=80.0), 0.30)
    assert next(c for c in r.checks if c.name == "mixed_air_freeze").passed
    r = run(box(freeze_f=82.0), 0.30)
    assert not next(c for c in r.checks if c.name == "mixed_air_freeze").passed


def test_freeze_check_skipped_when_not_set():
    assert all(c.name != "mixed_air_freeze" for c in run(box(), 0.30).checks)
