"""Print real failure messages from engine runs, for the M2 gate review.

Usage (from engine/):  python examples/failure_messages.py
Each case is a real solve or check on the §6.1 unit (or a small variant of it).
"""

import copy
import json
from pathlib import Path

from ahuverify import schema
from ahuverify.analysis import scenario
from ahuverify.checks import mode_coverage, static_checks
from ahuverify.controls import limit_failures
from ahuverify.failures import non_monotonic
from ahuverify.lanes import compile_unit
from ahuverify.schema import UnitConfig
from ahuverify.solver import solve
from ahuverify.state import AirState

FIX = Path(__file__).parents[1] / "tests" / "fixtures"
BASE = json.loads((FIX / "example_6_1.json").read_text())


def config(*mutations) -> UnitConfig:
    d = copy.deepcopy(BASE)
    for m in mutations:
        m(d)
    return UnitConfig.model_validate(d)


def mode(mid, schedule, loops=(), fixed=None):
    def m(d):
        d["sequence"]["modes"].append(
            {
                "id": mid,
                "priority": 1,
                "enter": {"var": "schedule", "op": "==", "value": schedule},
                "loops": list(loops),
                "fixed": fixed or {},
            }
        )

    return m


def loop(lid, setpoint_f, *actuators):
    def m(d):
        d["sequence"]["loops"][lid] = {
            "sensor": "SAT",
            "setpoint": {"value": setpoint_f, "unit": "F"},
            "stages": [{"actuator": a, "action": "direct"} for a in actuators],
        }

    return m


def cond(cid, oa_db, ra_db, ra_rh, schedule, oa_wb=None, oa_rh=None):
    c = {
        "id": cid,
        "oa_db": {"value": oa_db, "unit": "F"},
        "ra_db": {"value": ra_db, "unit": "F"},
        "ra_rh": {"value": ra_rh, "unit": "%"},
        "schedule": schedule,
    }
    c["oa_wb" if oa_wb is not None else "oa_rh"] = {
        "value": oa_wb if oa_wb is not None else oa_rh,
        "unit": "F" if oa_wb is not None else "%",
    }
    return schema.OperatingCondition.model_validate(c)


def first(failures, kind, contains=""):
    return next(f for f in failures if f.kind.value == kind and contains in f.message)


SUMMER = cond("summer_design", 91, 75, 50, "occupied", oa_wb=74)
cases = []

# 1, 2: summer cooling at design (F-16) — coil short, return damper fast
cool = config(
    mode("occupied_cooling", "occupied", ["sat_cooling"]),
    loop("sat_cooling", 55, "cc1.valve"),
)
run = scenario(cool, [SUMMER]).conditions[0]
cases.append(
    ("Summer design, cooling loop (F-16)", first(run.failures, "setpoint_not_met"))
)
cases.append(
    (
        "Summer design, minimum OA",
        first(run.failures, "limit_exceeded", "return damper"),
    )
)

# 3: warmup (F-12)
run = scenario(
    config(), [cond("winter_warmup", 13, 62, 30, "pre_occupancy", oa_rh=50)]
).conditions[0]
cases.append(
    (
        "Winter warmup, OA closed (F-12)",
        first(run.failures, "limit_exceeded", "mix1.ra"),
    )
)


# 4, 5: 12,000 cfm through the same unit — coil face velocity and fan design airflow
def bigger(d):
    d["airflows"]["supply"]["value"] = 12000


fast = config(
    bigger,
    mode("occupied_cooling", "occupied", ["sat_cooling"]),
    loop("sat_cooling", 55, "cc1.valve"),
)
run = scenario(fast, [SUMMER]).conditions[0]
cases.append(
    ("12,000 cfm supply", first(run.failures, "limit_exceeded", "Cooling coil"))
)
cases.append(("12,000 cfm supply", first(run.failures, "limit_exceeded", "Fan sf1")))


# 6: sensible-only wheel in deep winter — frost
def sensible_wheel(d):
    d["components"]["erw1"]["eps_lat"] = 0.0


frosty = config(sensible_wheel, mode("occupied_heating", "occupied"))
run = scenario(
    frosty, [cond("winter_design", 5, 72, 30, "occupied", oa_rh=60)]
).conditions[0]
cases.append(
    (
        "Wheel with no latent recovery, 5 °F OA",
        first(run.failures, "limit_exceeded", "frost"),
    )
)

# 7: preheat and cooling both on
fight = config(
    mode("bad_fixed", "occupied", fixed={"phc1.valve": 0.4, "cc1.valve": 0.6})
)
run = scenario(fight, [SUMMER]).conditions[0]
cases.append(("Preheat fixed open while cooling", first(run.failures, "fighting")))

# 8: economizer opened on a hot humid day
econ = config(
    mode("warm_by_oa", "occupied", ["sat_warm"]),
    loop("sat_warm", 82, "mix1.oa_fraction"),
)
run = scenario(econ, [SUMMER]).conditions[0]
cases.append(
    (
        "Economizer used to warm supply air on a humid day",
        first(run.failures, "fighting"),
    )
)

# 9: OA damper below minimum (solved directly, outside any mode)
cfg = config()
unit = compile_unit(cfg)
p = unit.p
oa, ra = AirState.from_db_wb(32.78, 23.33, p), AirState.from_db_rh(23.89, 0.5, p)
res = solve(
    unit,
    oa,
    ra,
    {"mix1.oa_fraction": 0.15, "cc1.valve": 1.0, "phc1.valve": 0.0, "rhc1.valve": 0.0},
)
cases.append(
    (
        "OA damper at 15 %",
        first(
            limit_failures(cfg, res, skip_oa_minimums=False),
            "limit_exceeded",
            "minimum",
        ),
    )
)

# 10, 11: mode coverage (F-14)
f14 = json.loads((FIX / "sequences" / "f14_modes.json").read_text())
f14.pop("_comment")
cov = mode_coverage(schema.Sequence.model_validate(f14), 101325.0)
cases.append(("F-14 sequence", first(cov, "mode_gap")))
cases.append(("F-14 sequence", first(cov, "mode_overlap")))


# 12: config error (F-15)
def drop_phc1(d):
    del d["components"]["phc1"]
    d["lanes"]["supply"].remove("phc1")


cases.append(
    (
        "Loop names a missing coil (F-15)",
        first(static_checks(config(drop_phc1)), "config_error"),
    )
)


# 13: static warning
def point_mat(d):
    d["sensors"][1]["type"] = "temperature"


cases.append(
    (
        "Single-point MAT sensor",
        first(static_checks(config(point_mat)), "config_error", "averaging"),
    )
)

# 14: non-monotonic (builder with real names; a real case needs a pathological unit)
cases.append(
    (
        "Wording only, for a stage whose effect reverses",
        non_monotonic("sat_cooling", "SAT", "mix1.oa_fraction"),
    )
)

print("| # | Case | Kind | Severity | Message |")
print("| --- | --- | --- | --- | --- |")
for n, (case, f) in enumerate(cases, 1):
    print(f"| {n} | {case} | `{f.kind.value}` | {f.severity} | {f.message} |")
