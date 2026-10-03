"""M2-6: analysis.scenario (spec §5.9)."""

import copy
import json
from pathlib import Path

import pytest

from ahuverify import analysis, controls, schema
from ahuverify.analysis import scenario
from ahuverify.failures import FailureKind
from ahuverify.schema import UnitConfig

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "example_6_1.json").read_text()
)


def cfg_with_cooling(mutate=None):
    d = copy.deepcopy(FIXTURE)
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
    if mutate:
        mutate(d)
    return UnitConfig.model_validate(d)


def cond(**kw):
    return schema.OperatingCondition.model_validate(kw)


SUMMER = cond(
    id="summer_design",
    oa_db={"value": 91, "unit": "F"},
    oa_wb={"value": 74, "unit": "F"},
    ra_db={"value": 75, "unit": "F"},
    ra_rh={"value": 50, "unit": "%"},
    schedule="occupied",
)
WARMUP = cond(
    id="winter_warmup",
    oa_db={"value": 13, "unit": "F"},
    oa_rh={"value": 50, "unit": "%"},
    ra_db={"value": 62, "unit": "F"},
    ra_rh={"value": 30, "unit": "%"},
    schedule="pre_occupancy",
)
NIGHT = cond(
    id="night",
    oa_db={"value": 50, "unit": "F"},
    oa_rh={"value": 50, "unit": "%"},
    ra_db={"value": 70, "unit": "F"},
    ra_rh={"value": 30, "unit": "%"},
    schedule="unoccupied",
)


def test_scenario_runs_each_condition():
    run = scenario(cfg_with_cooling(), [SUMMER, WARMUP, NIGHT])
    by_id = {r.condition_id: r for r in run.conditions}
    assert by_id["summer_design"].mode == "occupied_cooling"
    assert by_id["winter_warmup"].mode == "warmup"
    assert by_id["night"].mode is None
    assert by_id["night"].failures[0].kind == FailureKind.MODE_GAP
    s = by_id["summer_design"]
    assert s.positions["cc1.valve"] == 1.0
    assert "after:sf1" in s.result.states and "cc1" in s.result.components
    kinds = {f.kind for f in s.failures}
    assert FailureKind.SETPOINT_NOT_MET in kinds and FailureKind.LIMIT_EXCEEDED in kinds


def test_failures_carry_condition_and_mode():
    run = scenario(cfg_with_cooling(), [SUMMER])
    for f in run.conditions[0].failures:
        assert f.condition_id == "summer_design" and f.mode == "occupied_cooling"


def test_f15_config_error_stops_before_any_solve(monkeypatch):
    def no_solve(*a, **k):
        raise AssertionError("solve must not run on a config with errors")

    monkeypatch.setattr(controls, "solve", no_solve)
    monkeypatch.setattr(analysis, "run_condition", no_solve)

    def drop_phc1(d):
        del d["components"]["phc1"]
        d["lanes"]["supply"].remove("phc1")

    run = scenario(cfg_with_cooling(drop_phc1), [SUMMER, WARMUP])
    for r in run.conditions:
        assert r.result is None
        assert r.failures[0].kind == FailureKind.CONFIG_ERROR
        assert "phc1" in r.failures[0].message


def test_condition_needs_wb_or_rh_not_both():
    with pytest.raises(ValueError):
        cond(
            id="x",
            oa_db={"value": 70, "unit": "F"},
            ra_db={"value": 70, "unit": "F"},
            ra_rh={"value": 50, "unit": "%"},
        )
