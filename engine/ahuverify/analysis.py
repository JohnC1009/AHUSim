"""Analysis runs (spec §5.9). M2: scenario. Sweep and annual arrive in M4."""

from dataclasses import dataclass, field, replace

from ahuverify import schema
from ahuverify.checks import static_checks
from ahuverify.controls import ConditionInputs, run_condition
from ahuverify.failures import Failure, FailureKind
from ahuverify.lanes import ConfigError, compile_unit
from ahuverify.solver import SolveResult
from ahuverify.state import AirState


@dataclass
class ConditionResult:
    condition_id: str
    mode: str | None
    positions: dict[str, float]
    result: SolveResult | None  # states, component loads and checks
    failures: list[Failure] = field(default_factory=list)


@dataclass
class ScenarioRun:
    static: list[Failure]  # static checks: config errors, warnings, mode coverage
    conditions: list[ConditionResult]


def condition_inputs(c: schema.OperatingCondition, p: float) -> ConditionInputs:
    oa = (
        AirState.from_db_wb(c.oa_db.si, c.oa_wb.si, p)
        if c.oa_wb is not None
        else AirState.from_db_rh(c.oa_db.si, c.oa_rh.si, p)
    )
    ra = AirState.from_db_rh(c.ra_db.si, c.ra_rh.si, p)
    return ConditionInputs(
        oa, ra, c.schedule, None if c.space_t is None else c.space_t.si
    )


def _tag(failures: list[Failure], condition_id: str, mode: str | None) -> list[Failure]:
    return [
        replace(f, condition_id=condition_id, mode=f.mode or mode) for f in failures
    ]


def scenario(
    cfg: schema.UnitConfig, conditions: list[schema.OperatingCondition]
) -> ScenarioRun:
    """Run each named condition: mode, states, actuator positions, loads,
    checks and failures. Static config errors stop the run before any solve;
    every condition then reports them."""
    static = static_checks(cfg)
    blocking = [
        f
        for f in static
        if f.kind == FailureKind.CONFIG_ERROR and f.severity == "error"
    ]
    if blocking:
        return ScenarioRun(
            static,
            [
                ConditionResult(c.id, None, {}, None, _tag(blocking, c.id, None))
                for c in conditions
            ],
        )
    unit = compile_unit(cfg)
    results = []
    for c in conditions:
        try:
            out = run_condition(unit, cfg, condition_inputs(c, unit.p))
        except ConfigError as e:
            results.append(
                ConditionResult(
                    c.id,
                    None,
                    {},
                    None,
                    [Failure(FailureKind.CONFIG_ERROR, str(e), condition_id=c.id)],
                )
            )
            continue
        results.append(
            ConditionResult(
                c.id,
                out.mode,
                out.positions,
                out.result,
                _tag(out.failures, c.id, out.mode),
            )
        )
    return ScenarioRun(static, results)
