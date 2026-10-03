"""M1-8: lanes -> solve order, forward solve with residuals, space node (spec §5.5)."""

import copy
import json
from pathlib import Path

import pytest

from ahuverify import units
from ahuverify.failures import FailureKind
from ahuverify.lanes import ConfigError, compile_unit
from ahuverify.schema import UnitConfig
from ahuverify.solver import solve
from ahuverify.state import AirState

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "example_6_1.json").read_text()
)


def F(t_f: float) -> float:
    return units.to_si(t_f, "F")


def config(mutate=None) -> UnitConfig:
    data = copy.deepcopy(FIXTURE)
    if mutate:
        mutate(data)
    return UnitConfig.model_validate(data)


UNIT = compile_unit(config())
P = UNIT.p
SUMMER = {
    "oa": AirState.from_db_wb(F(91.0), F(74.0), P),
    "ra": AirState.from_db_rh(F(75.0), 0.50, P),
    "actuators": {
        "mix1.oa_fraction": 0.30,
        "cc1.valve": 1.0,
        "phc1.valve": 0.0,
        "rhc1.valve": 0.0,
    },
}


# ---------- compile-time validation ----------


def test_pressure_from_altitude():
    # 33 ft standard atmosphere
    assert P == pytest.approx(
        101325 * (1 - 2.25577e-5 * 33 * 0.3048) ** 5.2559, rel=1e-6
    )


def test_pressure_override():
    def m(d):
        d["unit"]["pressure_override"] = {"value": 100000, "unit": "Pa"}

    assert compile_unit(config(m)).p == 100000


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda d: d["lanes"]["supply"].__setitem__(0, "ra"), "supply lane must start"),
        (lambda d: d["lanes"]["supply"].append("zz9"), "zz9"),
        (lambda d: d["lanes"]["return"].remove("erw1.exhaust"), "erw1"),
        (
            lambda d: (d["lanes"]["supply"].remove("sf1"), d["components"].pop("sf1")),
            "end at a fan",
        ),
        (lambda d: d["lanes"]["supply"].remove("flt1"), "flt1 is not placed"),
        (lambda d: d["lanes"]["supply"].insert(4, "cc1"), "more than once"),
        (
            lambda d: (
                d["components"].__setitem__("mix2", d["components"]["mix1"]),
                d["lanes"]["supply"].insert(3, "mix2"),
                d["lanes"]["return"].insert(2, "mix2"),
            ),
            "one mixing box",
        ),
    ],
)
def test_config_errors_in_plain_english(mutate, message):
    with pytest.raises(ConfigError, match=message):
        compile_unit(config(mutate))


# ---------- forward solve ----------


def test_summer_solve_converges_and_closes():
    r = solve(UNIT, **SUMMER)
    assert r.converged and r.valid, r.failures
    for name, comp in r.components.items():
        assert all(abs(x) < 1e-3 for x in comp.residuals.values()), (
            name,
            comp.residuals,
        )


def test_airflows_match_config():
    r = solve(UNIT, **SUMMER)
    sa = r.states["after:sf1"]
    assert units.from_si(sa.m_da * sa.state.v, "cfm") == pytest.approx(10000, rel=1e-6)
    ra = r.states["ra"]
    assert units.from_si(ra.m_da * ra.state.v, "cfm") == pytest.approx(9800, rel=1e-6)
    mix = r.components["mix1"].loads
    assert mix["m_oa"] + (ra.m_da - mix["m_relief"]) == pytest.approx(sa.m_da, rel=1e-9)


def test_whole_unit_energy_and_water_balance():
    r = solve(UNIT, **SUMMER)
    m_in = [r.states["oa_intake"], r.states["ra"]]
    m_out = [r.states["after:sf1"], r.states["after:ef1"]]
    loads = [c.loads for c in r.components.values()]
    heat_in = (
        sum(L.get("q_air", 0.0) for L in loads) - r.components["cc1"].loads["q_total"]
    )
    water_out = sum(L.get("condensate", 0.0) for L in loads)
    e_in = sum(s.m_da * s.state.h for s in m_in) + heat_in / 1000
    e_out = sum(s.m_da * s.state.h for s in m_out)
    w_in = sum(s.m_da * s.state.w for s in m_in)
    w_out = sum(s.m_da * s.state.w for s in m_out) + water_out
    assert sum(s.m_da for s in m_in) == pytest.approx(
        sum(s.m_da for s in m_out), rel=1e-6
    )
    assert e_out == pytest.approx(e_in, rel=1e-4)
    assert w_out == pytest.approx(w_in, rel=1e-6)


def test_cooling_happens_and_fan_heat_follows():
    r = solve(UNIT, **SUMMER)
    after_cc = r.states["after:cc1"].state.t_db
    sat = r.states["after:sf1"].state.t_db
    assert after_cc < SUMMER["ra"].t_db
    assert sat > after_cc  # draw-through fan heat, filter ΔP included


def test_missing_actuator_is_a_config_error():
    with pytest.raises(ConfigError, match="cc1.valve"):
        solve(
            UNIT,
            SUMMER["oa"],
            SUMMER["ra"],
            {"mix1.oa_fraction": 0.3, "phc1.valve": 0, "rhc1.valve": 0},
        )


def test_non_convergence_is_reported():
    r = solve(UNIT, **SUMMER, max_passes=1)
    assert not r.converged and not r.valid
    assert r.failures[0].kind == FailureKind.NON_CONVERGED


# ---------- space node ----------


def with_space(sensible_mbh=150.0, latent_mbh=30.0):
    def m(d):
        d["components"]["space1"] = {
            "type": "space",
            "sensible_load": {"value": sensible_mbh, "unit": "MBH"},
            "latent_load": {"value": latent_mbh, "unit": "MBH"},
            "t_max": {"value": 78, "unit": "F"},
        }

    return compile_unit(config(m))


def test_space_node_closes_the_loop():
    unit = with_space()
    r = solve(unit, **SUMMER)
    assert r.converged and r.valid, r.failures
    sa, room = r.states["after:sf1"], r.states["ra"]
    q = (sa.m_da * (room.state.h - sa.state.h)) * 1000  # W
    assert q == pytest.approx(units.to_si(180.0, "MBH"), rel=1e-3)
    assert room.state.w > sa.state.w


def test_space_without_loads_returns_supply_state():
    r = solve(with_space(0.0, 0.0), **SUMMER)
    assert r.states["ra"].state.t_db == pytest.approx(
        r.states["after:sf1"].state.t_db, abs=0.01
    )


def test_space_range_check():
    r = solve(with_space(sensible_mbh=400.0), **SUMMER)
    check = next(c for c in r.components["space1"].checks if c.name == "t_max")
    assert not check.passed


def test_solve_with_oa_damper_closed():
    # Warmup (spec §6.1 / F-12): OA closed, so recirculation carries all supply air.
    acts = {**SUMMER["actuators"], "mix1.oa_fraction": 0.0, "cc1.valve": 0.0}
    r = solve(UNIT, SUMMER["oa"], SUMMER["ra"], acts)
    assert r.converged and r.valid, r.failures
    assert r.components["mix1"].loads["m_oa"] == 0.0
    ra_damper = next(
        c for c in r.components["mix1"].checks if c.name == "face_velocity_ra"
    )
    assert not ra_damper.passed
