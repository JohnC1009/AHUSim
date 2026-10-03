"""Limit checks pass within 0.01 % of the limit, so a value a search lands on
the limit is not failed by round-off — but any real exceedance fails."""

from ahuverify.components import at_least, at_most


def test_round_off_at_the_limit_passes():
    assert at_least("min_oa", 2999.99, 3000.0, "cfm").passed
    assert at_most("face_velocity", 1500.01, 1500.0, "fpm").passed


def test_real_exceedance_fails():
    assert not at_least("min_oa", 2999.0, 3000.0, "cfm").passed
    assert not at_most("face_velocity", 1501.0, 1500.0, "fpm").passed
