"""M2-4: failure model and messages; F-12 (spec §5.7)."""

import copy
import json
from pathlib import Path

import pytest

from ahuverify import units
from ahuverify.components import Check
from ahuverify.controls import ConditionInputs, run_condition
from ahuverify.failures import FailureKind, from_check
from ahuverify.lanes import compile_unit
from ahuverify.schema import UnitConfig
from ahuverify.state import AirState

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "example_6_1.json").read_text()
)


def F(t_f):
    return units.to_si(t_f, "F")


def outcome(mutate, oa, ra, schedule):
    data = copy.deepcopy(FIXTURE)
    mutate(data)
    cfg = UnitConfig.model_validate(data)
    unit = compile_unit(cfg)
    p = unit.p
    return run_condition(unit, cfg, ConditionInputs(oa(p), ra(p), schedule))


def winter_oa(p):
    return AirState.from_db_rh(F(13), 0.5, p)


def cold_room(p):
    return AirState.from_db_rh(F(62), 0.3, p)


def summer_oa(p):
    return AirState.from_db_wb(F(91), F(74), p)


def summer_ra(p):
    return AirState.from_db_rh(F(75), 0.5, p)


def of_kind(out, kind):
    return [f for f in out.failures if f.kind == kind]


def test_f12_warmup_return_damper_over_velocity():
    out = outcome(lambda d: None, winter_oa, cold_room, "pre_occupancy")
    assert out.mode == "warmup"
    (f,) = [
        f for f in of_kind(out, FailureKind.LIMIT_EXCEEDED) if f.component == "mix1.ra"
    ]
    fpm = units.from_si(f.value, "fpm")
    # Spec: ≈ 2,220 fpm (10,000 cfm / 4.5 ft²). On a mass basis the recirculated
    # air is cooler and denser than the 90 °F supply, so somewhat less.
    assert 2050 < fpm < 2250
    assert units.from_si(f.limit, "fpm") == pytest.approx(1500)
    assert (
        "mix1.ra" in f.message
        and "return damper" in f.message.lower()
        and "fpm" in f.message
    )


def test_fixed_oa_position_suppresses_min_oa_and_bias():
    out = outcome(lambda d: None, winter_oa, cold_room, "pre_occupancy")
    names = {f.component for f in of_kind(out, FailureKind.LIMIT_EXCEEDED)}
    assert "mix1.min_oa" not in names and "mix1.pressurization_bias" not in names


def fix(**positions):
    def m(d):
        d["sequence"]["modes"].append(
            {
                "id": "test",
                "priority": 1,
                "enter": {"var": "schedule", "op": "==", "value": "occupied"},
                "fixed": positions,
            }
        )

    return m


def test_preheat_while_cooling_is_fighting():
    out = outcome(
        fix(**{"phc1.valve": 0.4, "cc1.valve": 0.6}), summer_oa, summer_ra, "occupied"
    )
    (f,) = of_kind(out, FailureKind.FIGHTING)
    assert "phc1" in f.message and "cc1" in f.message


def test_cooling_with_downstream_reheat_is_not_fighting():
    out = outcome(
        fix(**{"rhc1.valve": 0.4, "cc1.valve": 0.6}), summer_oa, summer_ra, "occupied"
    )
    assert not of_kind(out, FailureKind.FIGHTING)


def test_economizer_above_minimum_with_hot_humid_oa_is_fighting():
    def m(d):
        d["sequence"]["modes"].append(
            {
                "id": "warm_by_oa",
                "priority": 1,
                "enter": {"var": "schedule", "op": "==", "value": "occupied"},
                "loops": ["sat_warm"],
            }
        )
        d["sequence"]["loops"]["sat_warm"] = {
            "sensor": "SAT",
            "setpoint": {"value": 82, "unit": "F"},
            "stages": [{"actuator": "mix1.oa_fraction", "action": "reverse"}],
        }

    out = outcome(m, summer_oa, summer_ra, "occupied")
    (f,) = of_kind(out, FailureKind.FIGHTING)
    assert "mix1" in f.message and "Btu/lb" in f.message


@pytest.mark.parametrize(
    "ctype, check, words",
    [
        (
            "energy_wheel",
            Check("frost", -4.0, 0.0, "C", False),
            ["erw1", "frost", "24.8 °F"],
        ),
        (
            "fan",
            Check("airflow", 5.0, 4.719474, "m3/s", False),
            ["sf1", "10,594 cfm", "10,000 cfm"],
        ),
        (
            "heating_coil_hw",
            Check("face_velocity", 2.8, 2.54, "m/s", False),
            ["phc1", "551 fpm", "500 fpm"],
        ),
        (
            "mixing_box",
            Check("mixed_air_freeze", 2.0, 3.333, "C", False),
            ["mix1", "35.6 °F", "38.0 °F"],
        ),
    ],
)
def test_check_messages_are_plain_ip_sentences(ctype, check, words):
    name = {
        "energy_wheel": "erw1",
        "fan": "sf1",
        "heating_coil_hw": "phc1",
        "mixing_box": "mix1",
    }[ctype]
    f = from_check(name, ctype, check)
    assert f.kind == FailureKind.LIMIT_EXCEEDED
    for w in words:
        assert w in f.message, (w, f.message)
    assert f.message.endswith(".") and ". " not in f.message  # one sentence
