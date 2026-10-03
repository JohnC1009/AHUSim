"""M1-5: hot-water coil (ε-NTU from rating) and electric heater; F-10."""

import pytest

from ahuverify import schema, units
from ahuverify.components.electric_heater import ElectricHeater
from ahuverify.components.heating_coil import (
    HeatingCoilHw,
    crossflow_unmixed_effectiveness,
)
from ahuverify.state import AirState, AirStream

P = 101325.0


def F(t_f: float) -> float:
    return units.to_si(t_f, "F")


def coil(max_fpm=None) -> HeatingCoilHw:
    cfg = schema.HeatingCoilHw.model_validate(
        {
            "type": "heating_coil_hw",
            "face_area": {"value": 22, "unit": "ft2"},
            **(
                {"max_face_velocity": {"value": max_fpm, "unit": "fpm"}}
                if max_fpm
                else {}
            ),
            "rating": {
                "eat": {"value": 40, "unit": "F"},
                "lat": {"value": 90, "unit": "F"},
                "airflow": {"value": 10000, "unit": "cfm"},
                "ewt": {"value": 180, "unit": "F"},
                "lwt": {"value": 160, "unit": "F"},
            },
        }
    )
    return HeatingCoilHw("phc1", cfg, p=P)


def rating_inlet(t_c=None) -> AirStream:
    """Rated mass flow (10,000 cfm at 40 °F, 50 % RH) at t_c (default EAT), 50 % RH."""
    eat = AirState.from_db_rh(F(40), 0.5, P)
    m = units.to_si(10000, "cfm") / eat.v
    return AirStream(
        AirState.from_db_rh(t_c if t_c is not None else eat.t_db, 0.5, P), m
    )


def test_effectiveness_limits():
    assert crossflow_unmixed_effectiveness(0.0001, 0.5) == pytest.approx(
        0.0001, rel=1e-2
    )
    # Approaches 1 slowly (exponent goes as NTU^0.22).
    assert 0.97 < crossflow_unmixed_effectiveness(20.0, 0.5) < 1.0
    assert crossflow_unmixed_effectiveness(
        100.0, 0.5
    ) > crossflow_unmixed_effectiveness(20.0, 0.5)
    # Incropera Fig. 11.18: Cr = 0.5, NTU = 1 -> ε ≈ 0.55
    assert crossflow_unmixed_effectiveness(1.0, 0.5) == pytest.approx(0.55, abs=0.02)


def test_f10_reproduces_rating():
    r = coil().solve({"in": rating_inlet()}, {"valve": 1.0}, P)
    assert r.outlets["out"].state.t_db == pytest.approx(F(90), abs=0.1)
    assert all(abs(x) < 1e-3 for x in r.residuals.values())


def test_f10_colder_air_more_output():
    c = coil()
    q_rated = c.solve({"in": rating_inlet()}, {"valve": 1.0}, P).loads["q_total"]
    q_cold = c.solve({"in": rating_inlet(F(40) - 10)}, {"valve": 1.0}, P).loads[
        "q_total"
    ]
    assert q_cold > q_rated


def test_valve_scales_output_linearly():
    c = coil()
    full = c.solve({"in": rating_inlet()}, {"valve": 1.0}, P).loads["q_total"]
    half = c.solve({"in": rating_inlet()}, {"valve": 0.5}, P).loads["q_total"]
    off = c.solve({"in": rating_inlet()}, {"valve": 0.0}, P)
    assert half == pytest.approx(0.5 * full)
    assert off.outlets["out"].state.t_db == pytest.approx(F(40), abs=1e-9)


def test_constant_humidity_ratio():
    inlet = rating_inlet()
    out = coil().solve({"in": inlet}, {"valve": 1.0}, P).outlets["out"].state
    assert out.w == inlet.state.w


def test_face_velocity_check():
    # 10,000 cfm / 22 ft² = 455 fpm
    assert (
        coil(max_fpm=500)
        .solve({"in": rating_inlet()}, {"valve": 1}, P)
        .checks[0]
        .passed
    )
    assert (
        not coil(max_fpm=400)
        .solve({"in": rating_inlet()}, {"valve": 1}, P)
        .checks[0]
        .passed
    )
    assert coil().solve({"in": rating_inlet()}, {"valve": 1}, P).checks == []


def heater(stages=None) -> ElectricHeater:
    cfg = schema.ElectricHeater.model_validate(
        {
            "type": "electric_heater",
            "power": {"value": 30, "unit": "kW"},
            **({"stages": stages} if stages else {}),
        }
    )
    return ElectricHeater("eh1", cfg)


def test_electric_heater_modulating_and_staged():
    inlet = rating_inlet()
    assert heater().solve({"in": inlet}, {"output": 0.5}, P).loads[
        "q_total"
    ] == pytest.approx(15000)
    # 3 stages: 0.5 -> 1 stage on (stage k on when output >= k/3)
    assert heater(3).solve({"in": inlet}, {"output": 0.5}, P).loads[
        "q_total"
    ] == pytest.approx(10000)
    r = heater(3).solve({"in": inlet}, {"output": 1.0}, P)
    assert r.loads["q_total"] == pytest.approx(30000)
    assert all(abs(x) < 1e-3 for x in r.residuals.values())
