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
    as_json = model.model_dump_json(by_alias=True)
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
