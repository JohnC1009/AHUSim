"""M1-9 harness: compare the cooling-coil model with manufacturer selections."""

from pathlib import Path

import pytest

from ahuverify.coil_validation import Selection, compare

SELECTIONS = sorted(
    (Path(__file__).parent / "fixtures" / "coil_selections").glob("*.json")
)


def test_example_selection_file_exists():
    assert any(p.name == "example_rated_point.json" for p in SELECTIONS)


@pytest.mark.parametrize("path", SELECTIONS, ids=lambda p: p.name)
def test_selection_files_load_and_compare(path):
    rows = compare(Selection.model_validate_json(path.read_text()))
    assert rows


def test_rated_point_compares_to_zero():
    path = next(p for p in SELECTIONS if p.name == "example_rated_point.json")
    (row,) = compare(Selection.model_validate_json(path.read_text()))
    assert abs(row.d_lat_db_f) < 0.1
    assert abs(row.d_lat_wb_f) < 0.1
    assert abs(row.d_q_pct) < 0.5
    assert row.within_limits
