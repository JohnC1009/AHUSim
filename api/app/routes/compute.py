"""Engine endpoints: solve, scenario, checks, chart grid, schema (spec §7)."""

from typing import Literal

from ahuverify.analysis import scenario
from ahuverify.chart import chart_grid
from ahuverify.checks import static_checks
from ahuverify.lanes import site_pressure
from ahuverify.report import condition_report, failure_report
from ahuverify.schema import OperatingCondition, UnitConfig, export_json_schema
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.auth import current_user

router = APIRouter(prefix="/v1", dependencies=[Depends(current_user)])
UnitSystem = Literal["ip", "si"]


class SolveRequest(BaseModel):
    config: UnitConfig
    condition: OperatingCondition
    units: UnitSystem = "ip"


class ScenarioRequest(BaseModel):
    config: UnitConfig
    conditions: list[OperatingCondition]
    units: UnitSystem = "ip"


class ChecksRequest(BaseModel):
    config: UnitConfig


@router.post("/solve")
def solve_one(body: SolveRequest) -> dict:
    run = scenario(body.config, [body.condition])
    return {
        "p": site_pressure(body.config.unit),
        "static": [failure_report(f) for f in run.static],
        "result": condition_report(run.conditions[0], body.units),
    }


@router.post("/scenario")
def solve_scenario(body: ScenarioRequest) -> dict:
    run = scenario(body.config, body.conditions)
    return {
        "p": site_pressure(body.config.unit),
        "static": [failure_report(f) for f in run.static],
        "results": [condition_report(c, body.units) for c in run.conditions],
    }


@router.post("/checks")
def checks(body: ChecksRequest) -> dict:
    return {"failures": [failure_report(f) for f in static_checks(body.config)]}


@router.get("/chart-grid")
def chart(
    p: float = Query(101325.0, gt=50000, lt=120000), units: UnitSystem = "ip"
) -> dict:
    return chart_grid(p, units)


@router.get("/schema")
def config_schema() -> dict:
    return export_json_schema()
