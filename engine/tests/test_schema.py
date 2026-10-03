"""M0-3: schema round-trip and JSON Schema export (spec §6, §10.3)."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ahuverify.schema import UnitConfig, export_json_schema

FIXTURES = Path(__file__).parent / "fixtures"
CONFIGS = sorted(FIXTURES.glob("*.json"))


def load(path: Path) -> dict:
    return json.loads(path.read_text())


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.name)
def test_round_trip_is_identical(path):
    original = load(path)
    model = UnitConfig.model_validate(original)
    # exclude_unset: write back only what was entered (optional fields left out stay out).
    as_json = model.model_dump_json(by_alias=True, exclude_unset=True)
    again = UnitConfig.model_validate_json(as_json)
    assert again == model
    # Nothing added, nothing lost, relative to the file on disk.
    assert json.loads(as_json) == original


def test_example_keeps_units_as_entered():
    cfg = UnitConfig.model_validate(load(FIXTURES / "example_6_1.json"))
    assert cfg.airflows.supply.value == 10000
    assert cfg.airflows.supply.unit == "cfm"
    assert cfg.lanes.return_[0] == "ra"


def test_unknown_key_rejected():
    data = load(FIXTURES / "example_6_1.json")
    data["unit"]["altitud"] = {"value": 0, "unit": "ft"}
    with pytest.raises(ValidationError):
        UnitConfig.model_validate(data)


def test_unsupported_unit_rejected():
    data = load(FIXTURES / "example_6_1.json")
    data["airflows"]["supply"]["unit"] = "gpm"
    with pytest.raises(ValidationError):
        UnitConfig.model_validate(data)


def test_condition_value_must_match_variable():
    data = load(FIXTURES / "example_6_1.json")
    # space_t compared against a schedule name instead of a temperature
    data["sequence"]["modes"][0]["enter"]["all"][1]["value"] = "occupied"
    with pytest.raises(ValidationError, match="needs a temperature"):
        UnitConfig.model_validate(data)


def test_export_json_schema():
    schema = export_json_schema()
    json.dumps(schema)  # serialisable
    assert set(schema["required"]) == {
        "schema_version",
        "unit",
        "airflows",
        "lanes",
        "components",
        "sensors",
        "sequence",
        "conditions",
    }
    assert "return" in schema["$defs"]["Lanes"]["properties"]


def test_cooling_coil_max_face_velocity_optional():
    data = load(FIXTURES / "example_6_1.json")
    cfg = UnitConfig.model_validate(data)
    assert cfg.components["cc1"].max_face_velocity is None  # not set: check skipped

    data["components"]["cc1"]["max_face_velocity"] = {"value": 500, "unit": "fpm"}
    cfg = UnitConfig.model_validate(data)
    assert cfg.components["cc1"].max_face_velocity.value == 500

    data["components"]["cc1"]["max_face_velocity"]["unit"] = "cfm"
    with pytest.raises(ValidationError):
        UnitConfig.model_validate(data)
