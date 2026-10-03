"""M1-1: unit conversions at the schema boundary (spec §4, §10.3)."""

import pytest

from ahuverify import units

ALL_UNITS = sorted(units.SUPPORTED_UNITS)


@pytest.mark.parametrize("unit", ALL_UNITS)
def test_round_trip_to_si_and_back(unit):
    for value in (-40.0, 0.0, 1.0, 72.5, 10000.0):
        back = units.from_si(units.to_si(value, unit), unit)
        assert back == pytest.approx(value, rel=1e-9, abs=1e-9)


@pytest.mark.parametrize(
    "value, unit, si",
    [
        (32.0, "F", 0.0),
        (212.0, "F", 100.0),
        (1.0, "ft", 0.3048),
        (10000.0, "cfm", 4.719474432),
        (1500.0, "fpm", 7.62),
        (4.0, "in_wc", 996.3556),  # F-8: 4.0 in. w.c. = 996.4 Pa
        (1.0, "MBH", 293.07107),
        (100.0, "lb/h", 0.012599788),
        (50.0, "%", 0.5),
    ],
)
def test_known_conversions(value, unit, si):
    assert units.to_si(value, unit) == pytest.approx(si, rel=1e-6, abs=1e-9)


def test_enthalpy_datum_offset():
    # I-P enthalpy is zero for dry air at 0 °F; SI is zero at 0 °C.
    # Dry air at 0 °F is 1.006 kJ/kg·K × (−17.78 K) = −17.884 kJ/kg on the SI datum.
    assert units.to_si(0.0, "Btu/lb") == pytest.approx(-17.884, abs=1e-3)


def test_unknown_unit_rejected():
    with pytest.raises(KeyError):
        units.to_si(1.0, "furlong")


def test_ip_enthalpy_display_f5():
    # F-5: 70 °F, 50 % RH, sea level -> W = 54.48 gr/lb, h = 25.30 Btu/lb.
    # Must come from I-P equations, not h_SI / 2.326 (which gives ~17.6).
    t_c = units.to_si(70.0, "F")
    w = 54.48 / 7000.0
    assert units.enthalpy_ip(t_c, w) == pytest.approx(25.30, abs=0.01)


def test_psychrolib_copies_are_independent():
    from ahuverify.psychro import ip, si

    assert ip.isIP() and not si.isIP()


def test_every_schema_unit_has_a_conversion():
    import typing

    from ahuverify import schema

    for cls in schema.QUANTITY_TYPES:
        allowed = typing.get_args(cls.model_fields["unit"].annotation)
        assert set(allowed) <= units.SUPPORTED_UNITS, cls.__name__
        assert cls(value=1.0, unit=allowed[0]).si == units.to_si(1.0, allowed[0])
