"""M2-2: static mode coverage — MODE_GAP and MODE_OVERLAP (spec §5.6); F-14."""

import json
from pathlib import Path

from ahuverify import schema
from ahuverify.checks import mode_coverage
from ahuverify.failures import FailureKind

FIX = Path(__file__).parent / "fixtures"
P = 101325.0


def sequence(name: str) -> schema.Sequence:
    data = json.loads((FIX / "sequences" / name).read_text())
    data.pop("_comment", None)
    return schema.Sequence.model_validate(data)


def kinds(failures):
    return sorted(f.kind for f in failures)


def test_f14_one_overlap_one_gap():
    found = mode_coverage(sequence("f14_modes.json"), P)
    assert kinds(found) == [FailureKind.MODE_GAP, FailureKind.MODE_OVERLAP]
    gap = next(f for f in found if f.kind == FailureKind.MODE_GAP)
    overlap = next(f for f in found if f.kind == FailureKind.MODE_OVERLAP)
    assert "86" in gap.message and "113" in gap.message  # 30–45 °C in °F
    assert "heating" in overlap.message and "cooling" in overlap.message
    assert "48" in overlap.message and "52" in overlap.message  # 9–11 °C in °F


def test_full_coverage_reports_nothing():
    seq = schema.Sequence.model_validate(
        {
            "modes": [
                {
                    "id": "cold",
                    "priority": 1,
                    "enter": {
                        "var": "oa_db",
                        "op": "<",
                        "value": {"value": 15, "unit": "C"},
                    },
                },
                {
                    "id": "warm",
                    "priority": 2,
                    "enter": {
                        "var": "oa_db",
                        "op": ">=",
                        "value": {"value": 10, "unit": "C"},
                    },
                },
            ],
            "loops": {},
        }
    )
    assert mode_coverage(seq, P) == []  # overlap at different priorities is fine


def test_off_grid_variable_is_checked_at_its_thresholds():
    # §6.1 warmup only: active when pre_occupancy AND space_t < 68 °F.
    cfg = schema.UnitConfig.model_validate(
        json.loads((FIX / "example_6_1.json").read_text())
    )
    gaps = [f for f in mode_coverage(cfg.sequence, P) if f.kind == FailureKind.MODE_GAP]
    assert gaps, "space_t at or above 68 °F leaves no mode active"
    assert any("space_t" in f.message for f in gaps)
