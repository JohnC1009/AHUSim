"""M2-5: static configuration checks (spec §5.8); F-15."""

import copy
import json
from pathlib import Path

import pytest

from ahuverify.checks import static_checks
from ahuverify.failures import FailureKind
from ahuverify.schema import UnitConfig

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "example_6_1.json").read_text()
)


def checked(mutate=None):
    data = copy.deepcopy(FIXTURE)
    if mutate:
        mutate(data)
    return static_checks(UnitConfig.model_validate(data))


def errors(found):
    return [
        f for f in found if f.kind == FailureKind.CONFIG_ERROR and f.severity == "error"
    ]


def test_example_has_no_config_errors():
    found = checked()
    assert errors(found) == []
    assert not [
        f for f in found if f.severity == "warning"
    ]  # MAT is an averaging sensor


def test_f15_loop_names_missing_component():
    def m(d):
        del d["components"]["phc1"]
        d["lanes"]["supply"].remove("phc1")

    (f,) = errors(checked(m))
    assert (
        f.message
        == "Loop sat_heating names phc1.valve, but there is no component phc1."
    )


@pytest.mark.parametrize(
    "mutate, fragment",
    [
        (
            lambda d: d["sequence"]["loops"]["sat_heating"]["stages"][0].update(
                actuator="phc1.output"
            ),
            "phc1 has no actuator output",
        ),
        (
            lambda d: d["sequence"]["loops"]["sat_heating"].update(sensor="DAT"),
            "no sensor DAT",
        ),
        (lambda d: d["sensors"][0].update(at="after:zz9"), "SAT is placed after:zz9"),
        (lambda d: d["sequence"]["modes"][0]["loops"].append("econ"), "no loop econ"),
        (
            lambda d: d["sequence"]["modes"][0]["fixed"].update({"phc1.valve": 0.0}),
            "fixes phc1.valve and also",
        ),
        (
            lambda d: d["sequence"]["modes"][0]["fixed"].update({"cc9.valve": 0.0}),
            "no component cc9",
        ),
        (lambda d: d["airflows"]["min_oa"].update(value=12000), "minimum OA"),
        (lambda d: d["lanes"]["supply"].remove("sf1"), "sf1 is not placed"),
    ],
)
def test_config_errors(mutate, fragment):
    msgs = [f.message for f in errors(checked(mutate))]
    assert any(fragment in m for m in msgs), msgs


def preheat_loop(actuator):
    def m(d):
        d["sequence"]["loops"]["sat_heating"]["role"] = "preheat"
        d["sequence"]["loops"]["sat_heating"]["stages"][0]["actuator"] = actuator

    return m


def test_preheat_loop_must_act_upstream_of_cooling_coil():
    assert errors(checked(preheat_loop("phc1.valve"))) == []
    (f,) = errors(checked(preheat_loop("rhc1.valve")))
    assert "rhc1" in f.message and "upstream" in f.message
    # cc1 also collides with warmup's own "fixed: cc1.valve" — both are reported.
    msgs = [f.message for f in errors(checked(preheat_loop("cc1.valve")))]
    assert any("cc1" in m and "not a heating coil" in m for m in msgs), msgs
    assert any("fixes cc1.valve and also" in m for m in msgs), msgs


def test_non_averaging_mixed_air_sensor_is_a_warning():
    found = checked(lambda d: d["sensors"][1].update(type="temperature"))
    (w,) = [f for f in found if f.severity == "warning"]
    assert "MAT" in w.message and "averaging" in w.message
    assert errors(found) == []


def test_relief_negative_at_minimum_oa_is_a_warning():
    found = checked(lambda d: d["airflows"]["min_oa"].update(value=150))
    assert any(f.severity == "warning" and "relief" in f.message for f in found)
