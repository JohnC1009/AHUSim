"""M2-3: staged loop solver, monotonic check, outer iteration; F-16 (spec §5.6)."""

import copy
import json
import math
from pathlib import Path

import pytest

from ahuverify import units
from ahuverify.controls import ConditionInputs, run_condition, solve_staged_loop
from ahuverify.failures import FailureKind
from ahuverify.lanes import compile_unit
from ahuverify.schema import UnitConfig
from ahuverify.state import AirState

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "example_6_1.json").read_text()
)


def F(t_f):
    return units.to_si(t_f, "F")


# ---------- the staged algorithm on its own ----------


def test_first_stage_meets_setpoint_by_bisection():
    out = solve_staged_loop(
        "L",
        ["a", "b"],
        lambda p: 20 - 10 * p["a"] - 10 * p["b"],
        14.0,
        {"a": 0.0, "b": 0.0},
        {"a": (0, 1), "b": (0, 1)},
    )
    assert out.failure is None
    assert out.positions["a"] == pytest.approx(0.6, abs=1e-3)
    assert out.positions["b"] == 0.0


def test_stage_parks_at_full_then_next_stage_finishes():
    out = solve_staged_loop(
        "L",
        ["a", "b"],
        lambda p: 20 - 4 * p["a"] - 10 * p["b"],
        11.0,
        {"a": 0.0, "b": 0.0},
        {"a": (0, 1), "b": (0, 1)},
    )
    assert out.failure is None
    assert out.positions["a"] == 1.0
    assert out.positions["b"] == pytest.approx(0.5, abs=1e-3)


def test_stage_parks_at_the_end_nearer_the_setpoint():
    # Stage a moves PV away from the setpoint: it stays at its off end.
    out = solve_staged_loop(
        "L",
        ["a", "b"],
        lambda p: 20 + 5 * p["a"] - 10 * p["b"],
        15.0,
        {"a": 0.0, "b": 0.0},
        {"a": (0, 1), "b": (0, 1)},
    )
    assert out.positions["a"] == 0.0
    assert out.positions["b"] == pytest.approx(0.5, abs=1e-3)


def test_all_stages_parked_reports_setpoint_not_met():
    out = solve_staged_loop(
        "L", ["a"], lambda p: 20 - 4 * p["a"], 10.0, {"a": 0.0}, {"a": (0, 1)}
    )
    f = out.failure
    assert f.kind == FailureKind.SETPOINT_NOT_MET
    assert out.positions["a"] == 1.0
    assert f.value == pytest.approx(16.0) and f.limit == pytest.approx(10.0)


def test_non_monotonic_response_is_refused():
    out = solve_staged_loop(
        "L",
        ["a"],
        lambda p: 20 - 5 * math.sin(math.pi * p["a"]),
        17.0,
        {"a": 0.0},
        {"a": (0, 1)},
    )
    assert out.failure.kind == FailureKind.NON_MONOTONIC


def test_reverse_range_off_end_at_one():
    # Wheel bypass: off end is 1 (fully bypassed), on end is 0.
    out = solve_staged_loop(
        "L",
        ["byp"],
        lambda p: 10 + 8 * (1 - p["byp"]),
        14.0,
        {"byp": 1.0},
        {"byp": (1, 0)},
    )
    assert out.positions["byp"] == pytest.approx(0.5, abs=1e-3)


# ---------- on the §6.1 unit ----------


def unit_with(mutate):
    data = copy.deepcopy(FIXTURE)
    mutate(data)
    cfg = UnitConfig.model_validate(data)
    return cfg, compile_unit(cfg)


def add_cooling_mode(d):
    d["sequence"]["modes"].append(
        {
            "id": "occupied_cooling",
            "priority": 1,
            "enter": {"var": "schedule", "op": "==", "value": "occupied"},
            "loops": ["sat_cooling"],
        }
    )
    d["sequence"]["loops"]["sat_cooling"] = {
        "sensor": "SAT",
        "setpoint": {"value": 55, "unit": "F"},
        "stages": [{"actuator": "cc1.valve", "action": "direct"}],
    }


def test_f16_cooling_loop_beyond_coil_capacity():
    cfg, unit = unit_with(add_cooling_mode)
    p = unit.p
    inputs = ConditionInputs(
        AirState.from_db_wb(F(91), F(74), p),
        AirState.from_db_rh(F(75), 0.5, p),
        "occupied",
    )
    out = run_condition(unit, cfg, inputs)
    assert out.mode == "occupied_cooling"
    f = next(x for x in out.failures if x.kind == FailureKind.SETPOINT_NOT_MET)
    assert f.component == "sat_cooling"
    assert out.positions["cc1.valve"] == 1.0
    shortfall_k = f.value - f.limit
    assert 1.0 < shortfall_k < 2.0  # ~2.8 °F: draw-through fan heat after a 55 °F coil
    assert "cc1.valve" in f.message and "°F" in f.message


def test_warmup_loop_holds_90f_sat():
    cfg, unit = unit_with(lambda d: None)
    p = unit.p
    inputs = ConditionInputs(
        AirState.from_db_rh(F(13), 0.5, p),
        AirState.from_db_rh(F(62), 0.3, p),
        "pre_occupancy",
    )
    out = run_condition(unit, cfg, inputs)
    assert out.mode == "warmup"
    assert not [f for f in out.failures if f.kind == FailureKind.SETPOINT_NOT_MET]
    sat = out.result.states["after:sf1"].state.t_db
    assert sat == pytest.approx(F(90), abs=0.01)
    assert out.positions["mix1.oa_fraction"] == 0.0  # fixed by the mode
    assert 0.0 < out.positions["phc1.valve"] < 1.0


def test_min_oa_position_found_when_not_fixed():
    cfg, unit = unit_with(add_cooling_mode)
    p = unit.p
    inputs = ConditionInputs(
        AirState.from_db_wb(F(91), F(74), p),
        AirState.from_db_rh(F(75), 0.5, p),
        "occupied",
    )
    out = run_condition(unit, cfg, inputs)
    min_oa = next(c for c in out.result.components["mix1"].checks if c.name == "min_oa")
    assert units.from_si(min_oa.value, "cfm") == pytest.approx(3000, abs=1.0)


def test_no_active_mode_is_a_mode_gap():
    cfg, unit = unit_with(lambda d: None)
    p = unit.p
    inputs = ConditionInputs(
        AirState.from_db_rh(F(13), 0.5, p),
        AirState.from_db_rh(F(70), 0.3, p),
        "occupied",
    )
    out = run_condition(unit, cfg, inputs)
    assert out.mode is None and out.failures[0].kind == FailureKind.MODE_GAP
