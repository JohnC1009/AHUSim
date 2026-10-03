"""M2-1: structured conditions and mode selection (spec §5.6)."""

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from ahuverify import schema, units
from ahuverify.controls import ConditionInputs, evaluate, select_mode
from ahuverify.state import AirState

P = 101325.0
FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "example_6_1.json").read_text()
)
COND = TypeAdapter(schema.Condition)


def F(t_f):
    return units.to_si(t_f, "F")


def inputs(oa_f=40.0, oa_rh=0.5, ra_f=70.0, schedule="occupied", space_f=None):
    return ConditionInputs(
        oa=AirState.from_db_rh(F(oa_f), oa_rh, P),
        ra=AirState.from_db_rh(F(ra_f), 0.3, P),
        schedule=schedule,
        space_t=None if space_f is None else F(space_f),
    )


def cmp(var, op, value):
    return COND.validate_python({"var": var, "op": op, "value": value})


def test_temperature_comparison_in_either_unit():
    i = inputs(oa_f=40.0)
    assert evaluate(cmp("oa_db", "<", {"value": 41, "unit": "F"}), i)
    assert not evaluate(
        cmp("oa_db", "<", {"value": 4.0, "unit": "C"}), i
    )  # 40 °F = 4.44 °C
    assert evaluate(cmp("oa_db", "<=", {"value": 40, "unit": "F"}), i)


def test_enthalpy_in_btu_per_lb_is_exact():
    # 70 °F / 50 % RH -> 25.30 Btu/lb (F-5), compared with I-P equations.
    i = inputs(oa_f=70.0, oa_rh=0.5)
    assert evaluate(cmp("oa_h", ">", {"value": 25.29, "unit": "Btu/lb"}), i)
    assert not evaluate(cmp("oa_h", ">", {"value": 25.31, "unit": "Btu/lb"}), i)


def test_combinators():
    i = inputs(oa_f=40.0, schedule="occupied")
    cold = {"var": "oa_db", "op": "<", "value": {"value": 50, "unit": "F"}}
    occ = {"var": "schedule", "op": "==", "value": "occupied"}
    unocc = {"var": "schedule", "op": "==", "value": "unoccupied"}
    assert evaluate(COND.validate_python({"all": [cold, occ]}), i)
    assert not evaluate(COND.validate_python({"all": [cold, unocc]}), i)
    assert evaluate(COND.validate_python({"any": [unocc, cold]}), i)
    assert evaluate(COND.validate_python({"not": unocc}), i)


def test_space_t_defaults_to_return_air_temperature():
    lt68 = cmp("space_t", "<", {"value": 68, "unit": "F"})
    assert evaluate(lt68, inputs(ra_f=65.0))
    assert not evaluate(lt68, inputs(ra_f=70.0))
    assert evaluate(lt68, inputs(ra_f=70.0, space_f=60.0))


def test_schedule_only_compares_for_equality():
    with pytest.raises(ValidationError, match="schedule"):
        cmp("schedule", "<", "occupied")


def modes(*specs):
    return [schema.Mode.model_validate(m) for m in specs]


def test_select_mode_by_priority_first_true_wins():
    always = {"not": {"var": "schedule", "op": "==", "value": "never"}}
    ms = modes(
        {"id": "low", "priority": 5, "enter": always},
        {"id": "high", "priority": 1, "enter": always},
        {"id": "also_high", "priority": 1, "enter": always},
    )
    assert select_mode(ms, inputs()).id == "high"  # equal priority: declared order


def test_select_mode_example_warmup():
    cfg = schema.UnitConfig.model_validate(FIXTURE)
    warm = inputs(schedule="pre_occupancy", ra_f=65.0)
    assert select_mode(cfg.sequence.modes, warm).id == "warmup"
    assert (
        select_mode(cfg.sequence.modes, inputs(schedule="pre_occupancy", ra_f=70.0))
        is None
    )
    assert (
        select_mode(cfg.sequence.modes, inputs(schedule="occupied", ra_f=65.0)) is None
    )
