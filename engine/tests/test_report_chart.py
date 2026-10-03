"""M3-1 (engine side): display values in I-P or SI, and the psych-chart grid."""

import json
from pathlib import Path

import pytest

from ahuverify import schema, units
from ahuverify.analysis import scenario
from ahuverify.chart import chart_grid
from ahuverify.report import condition_report, state_row
from ahuverify.state import AirState, AirStream

FIX = Path(__file__).parent / "fixtures"


def test_state_row_ip_uses_ip_enthalpy():
    s = AirStream(AirState.from_db_rh(units.to_si(70, "F"), 0.5, 101325.0), 1.0)
    row = state_row("after:x", s, "ip")
    assert row["db"] == pytest.approx(70.0)
    assert row["w"] == pytest.approx(54.48, abs=0.01)  # gr/lb
    assert row["h"] == pytest.approx(25.30, abs=0.01)  # Btu/lb, F-5 — not h_SI / 2.326
    assert row["flow"] == pytest.approx(units.from_si(s.state.v, "cfm"))


def test_state_row_si():
    s = AirStream(AirState.from_db_rh(25.0, 0.5, 101325.0), 2.0)
    row = state_row("after:x", s, "si")
    assert row["db"] == pytest.approx(25.0) and row["w"] == pytest.approx(
        9.881, rel=1e-3
    )
    assert row["h"] == pytest.approx(50.322, rel=1e-3) and row["flow"] == pytest.approx(
        2.0 * s.state.v
    )


def test_condition_report_is_json_ready_in_display_units():
    cfg = schema.UnitConfig.model_validate(
        json.loads((FIX / "example_6_1.json").read_text())
    )
    c = schema.OperatingCondition.model_validate(
        {
            "id": "winter_warmup",
            "oa_db": {"value": 13, "unit": "F"},
            "oa_rh": {"value": 50, "unit": "%"},
            "ra_db": {"value": 62, "unit": "F"},
            "ra_rh": {"value": 30, "unit": "%"},
            "schedule": "pre_occupancy",
        }
    )
    rep = condition_report(scenario(cfg, [c]).conditions[0], "ip")
    json.dumps(rep)
    assert rep["mode"] == "warmup" and rep["units"]["db"] == "°F"
    sat = next(r for r in rep["states"] if r["key"] == "after:sf1")
    assert sat["db"] == pytest.approx(90.0, abs=0.02)
    ra_damper = next(
        c
        for c in rep["components"]["mix1"]["checks"]
        if c["name"] == "face_velocity_ra"
    )
    assert ra_damper["unit"] == "fpm" and ra_damper["limit"] == pytest.approx(1500)
    assert rep["failures"][0]["component"] == "mix1.ra"
    assert rep["components"]["phc1"]["loads"]["q_total"]["unit"] == "MBH"


@pytest.mark.parametrize("system", ["ip", "si"])
def test_chart_grid_lines(system):
    g = chart_grid(101325.0, system)
    kinds = {line["kind"] for line in g["lines"]}
    assert {"saturation", "rh", "db", "w", "h", "wb"} <= kinds
    assert len([ln for ln in g["lines"] if ln["kind"] == "rh"]) == 9  # 10 … 90 %
    sat = next(ln for ln in g["lines"] if ln["kind"] == "saturation")
    x0, x1 = g["x"]["min"], g["x"]["max"]
    y1 = g["y"]["max"]
    assert all(x0 <= x <= x1 and 0 <= y <= y1 for x, y in sat["points"])
    json.dumps(g)


def test_chart_grid_saturation_point_ip():
    g = chart_grid(101325.0, "ip")
    sat = next(ln for ln in g["lines"] if ln["kind"] == "saturation")
    x, y = min(sat["points"], key=lambda pt: abs(pt[0] - 70.0))
    # Saturation at 70 °F, sea level: W = 110.35 gr/lb (PsychroLib, I-P)
    assert x == pytest.approx(70.0, abs=0.5) and y == pytest.approx(110.35, abs=1.0)
