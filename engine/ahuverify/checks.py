"""Static checks: no weather needed, run on every config change (spec §5.6, §5.8)."""

from itertools import groupby

from ahuverify import schema, units
from ahuverify.controls import ConditionInputs, actuator_table, evaluate
from ahuverify.failures import Failure, FailureKind
from ahuverify.lanes import ConfigError, compile_unit, site_pressure
from ahuverify.psychro import si
from ahuverify.state import AirState

# Spec §5.6 grid: OA dry bulb −30…45 °C in 1 K steps × OA RH 10…100 % in 10 % steps.
GRID_DB = range(-30, 46)
GRID_RH = [r / 10 for r in range(1, 11)]
_DEFAULT_RA = (24.0, 0.5)  # °C, RH — used when no condition looks at return air
_STEP = {
    "ra_db": 0.05,
    "space_t": 0.05,
    "ra_h": 0.2,
}  # K, K, kJ/kg either side of a threshold


def _comparisons(cond: schema.Condition):
    if isinstance(cond, schema.AllOf):
        for c in cond.all:
            yield from _comparisons(c)
    elif isinstance(cond, schema.AnyOf):
        for c in cond.any:
            yield from _comparisons(c)
    elif isinstance(cond, schema.NotOf):
        yield from _comparisons(cond.not_)
    else:
        yield cond


def _thresholds(seq: schema.Sequence, var: str) -> list:
    return [c.value for m in seq.modes for c in _comparisons(m.enter) if c.var == var]


def _samples(seq: schema.Sequence, var: str) -> list[float]:
    """Values just below, at and just above each threshold on `var` (SI).

    Conditions compare a variable with constants, so a mode can only switch
    at a threshold: these samples cover every case exactly.
    """
    out = set()
    for q in _thresholds(seq, var):
        for d in (-_STEP[var], 0.0, _STEP[var]):
            out.add(q.si + d)
    return sorted(out)


def _return_air_samples(seq: schema.Sequence, p: float) -> list[tuple[AirState, str]]:
    dbs = _samples(seq, "ra_db") or [_DEFAULT_RA[0]]
    hs = _samples(seq, "ra_h")
    out = []
    for t in dbs:
        if not hs:
            label = (
                f"RA = {units.from_si(t, 'F'):.1f} °F"
                if _thresholds(seq, "ra_db")
                else ""
            )
            out.append((AirState.from_db_rh(t, _DEFAULT_RA[1], p), label))
            continue
        for h in hs:
            w = si.GetHumRatioFromEnthalpyAndTDryBulb(h * 1000.0, t)
            if 0.0 <= w <= si.GetSatHumRatio(t, p):
                out.append(
                    (
                        AirState(t, w, p),
                        f"RA = {units.from_si(t, 'F'):.1f} °F, {units.enthalpy_ip(t, w):.2f} Btu/lb",
                    )
                )
    return out


def _runs(points: set[tuple[int, float]]) -> list[tuple[int, int, float, float]]:
    """Contiguous OA dry-bulb runs: (db_lo, db_hi, rh_lo, rh_hi), °C and 0–1."""
    dbs = sorted({db for db, _ in points})
    runs = []
    for _, group in groupby(enumerate(dbs), key=lambda x: x[1] - x[0]):
        run = [db for _, db in group]
        rhs = [rh for db, rh in points if run[0] <= db <= run[-1]]
        runs.append((run[0], run[-1], min(rhs), max(rhs)))
    return runs


def _where(lo: int, hi: int, rh_lo: float, rh_hi: float) -> str:
    f_lo, f_hi = units.from_si(lo, "F"), units.from_si(hi, "F")
    db = f"OA {f_lo:.0f} °F" if lo == hi else f"OA {f_lo:.0f} to {f_hi:.0f} °F"
    rh = (
        f"{rh_lo * 100:.0f} % RH"
        if rh_lo == rh_hi
        else f"{rh_lo * 100:.0f}–{rh_hi * 100:.0f} % RH"
    )
    return f"{db} at {rh}"


def _when(schedule: str | None, extras: list[str]) -> str:
    parts = ([f"schedule = {schedule}"] if schedule else []) + [e for e in extras if e]
    return f" when {', '.join(parts)}" if parts else ""


def mode_coverage(seq: schema.Sequence, p: float) -> list[Failure]:
    """MODE_GAP where no mode is active; MODE_OVERLAP where two modes of the
    same priority are both active and that priority is the one that wins.

    Grid per spec §5.6, for each schedule value named in the conditions; RA and
    space temperature are taken at their thresholds (see _samples).
    """
    schedules = sorted(
        {
            c.value
            for m in seq.modes
            for c in _comparisons(m.enter)
            if c.var == "schedule"
        }
    ) or [None]
    space = [
        (t, f"space_t = {units.from_si(t, 'F'):.1f} °F")
        for t in _samples(seq, "space_t")
    ] or [(None, "")]
    oa = {
        (db, rh): AirState.from_db_rh(float(db), rh, p)
        for db in GRID_DB
        for rh in GRID_RH
    }

    found: dict[tuple, str] = {}  # (kind, modes, region) -> message; first context wins
    for schedule in schedules:
        for ra, ra_label in _return_air_samples(seq, p):
            for space_t, space_label in space:
                gaps, overlaps = set(), {}
                for key, state in oa.items():
                    i = ConditionInputs(state, ra, schedule, space_t)
                    active = [m for m in seq.modes if evaluate(m.enter, i)]
                    if not active:
                        gaps.add(key)
                        continue
                    top = min(m.priority for m in active)
                    tied = tuple(m.id for m in active if m.priority == top)
                    if len(tied) > 1:
                        overlaps.setdefault((tied, top), set()).add(key)
                when = _when(schedule, [ra_label, space_label])
                for run in _runs(gaps) if gaps else []:
                    found.setdefault(
                        (FailureKind.MODE_GAP, (), schedule, run),
                        f"No mode is active for {_where(*run)}{when}.",
                    )
                for (tied, top), pts in overlaps.items():
                    for run in _runs(pts):
                        names = " and ".join(tied)
                        found.setdefault(
                            (FailureKind.MODE_OVERLAP, tied, schedule, run),
                            f"Modes {names} (both priority {top}) are both active for {_where(*run)}{when}.",
                        )
    return [
        Failure(kind, message, mode=", ".join(modes) or None)
        for (kind, modes, _, _), message in found.items()
    ]


# ---------- configuration checks (spec §5.8) ----------

_HEATING = {"heating_coil_hw", "electric_heater"}


def _error(message: str, component: str | None = None) -> Failure:
    return Failure(FailureKind.CONFIG_ERROR, message, component=component)


def _warning(message: str, component: str | None = None) -> Failure:
    return Failure(
        FailureKind.CONFIG_ERROR, message, component=component, severity="warning"
    )


def _actuator_ref(
    cfg: schema.UnitConfig, owner: str, verb: str, ref: str
) -> list[Failure]:
    comp, _, act = ref.partition(".")
    if comp not in cfg.components:
        return [
            _error(f"{owner} {verb} {ref}, but there is no component {comp}.", comp)
        ]
    have = sorted(
        r.partition(".")[2] for r in actuator_table(cfg) if r.startswith(f"{comp}.")
    )
    if act not in have:
        listing = ", ".join(have) if have else "none"
        return [_error(f"{comp} has no actuator {act}; it has: {listing}.", comp)]
    return []


def _sequence_references(cfg: schema.UnitConfig) -> list[Failure]:
    out = []
    seq, sensors = cfg.sequence, {s.id for s in cfg.sensors}
    for lid, loop in seq.loops.items():
        if loop.sensor not in sensors:
            out.append(
                _error(
                    f"Loop {lid} reads sensor {loop.sensor}, but there is no sensor {loop.sensor}.",
                    lid,
                )
            )
        for st in loop.stages:
            out += _actuator_ref(cfg, f"Loop {lid}", "names", st.actuator)
    for mode in seq.modes:
        for ref in mode.fixed:
            out += _actuator_ref(cfg, f"Mode {mode.id}", "fixes", ref)
        for lid in mode.loops:
            if lid not in seq.loops:
                out.append(
                    _error(
                        f"Mode {mode.id} runs loop {lid}, but there is no loop {lid}."
                    )
                )
                continue
            for st in seq.loops[lid].stages:
                if st.actuator in mode.fixed:
                    out.append(
                        _error(
                            f"Mode {mode.id} fixes {st.actuator} and also drives it from loop {lid}."
                        )
                    )
    return out


def _lane_points(cfg: schema.UnitConfig) -> set[str]:
    box = next((c for c, m in cfg.components.items() if m.type == "mixing_box"), None)
    pts = {f"after:{t}" for t in cfg.lanes.supply[1:]}
    pts |= {f"after:{t}" for t in cfg.lanes.return_[1:] if t != box}
    if box:
        pts.add(f"after:{box}.relief")
    return pts


def _sensor_placement(cfg: schema.UnitConfig) -> list[Failure]:
    out, points = [], _lane_points(cfg)
    boxes = {c for c, m in cfg.components.items() if m.type == "mixing_box"}
    for s in cfg.sensors:
        if s.at not in points:
            out.append(
                _error(
                    f"Sensor {s.id} is placed {s.at}, which is not a point in the lanes.",
                    s.id,
                )
            )
        elif s.at.removeprefix("after:") in boxes and s.type == "temperature":
            out.append(
                _warning(
                    f"Mixed-air sensor {s.id} is a single-point temperature sensor; mixed air stratifies, "
                    f"so use an averaging sensor.",
                    s.id,
                )
            )
    return out


def _coil_order(cfg: schema.UnitConfig) -> list[Failure]:
    """Preheat / freeze-protection loops must drive a heater upstream of every cooling coil."""
    out = []
    supply = [t.partition(".")[0] for t in cfg.lanes.supply]
    coolers = [
        c
        for c in supply
        if c in cfg.components and cfg.components[c].type == "cooling_coil_chw"
    ]
    for lid, loop in cfg.sequence.loops.items():
        if loop.role is None:
            continue
        role = loop.role.replace("_", "-")
        for st in loop.stages:
            comp = st.actuator.partition(".")[0]
            model = cfg.components.get(comp)
            if model is None:
                continue  # reported by _sequence_references
            if model.type not in _HEATING:
                out.append(
                    _error(
                        f"Loop {lid} is a {role} loop but drives {comp}, which is not a heating coil.",
                        lid,
                    )
                )
                continue
            for cc in coolers:
                if comp in supply and supply.index(comp) > supply.index(cc):
                    out.append(
                        _error(
                            f"Loop {lid} is a {role} loop but {comp} is not upstream of cooling coil {cc}.",
                            lid,
                        )
                    )
    return out


def _airflow_closure(cfg: schema.UnitConfig) -> list[Failure]:
    """At minimum OA: supply = OA + recirculated, return = recirculated + relief."""
    a = cfg.airflows
    q_s, q_min, q_b = a.supply.si, a.min_oa.si, a.pressurization_bias.si
    cfm = lambda q: f"{units.from_si(q, 'cfm'):,.0f} cfm"
    out = []
    if q_min > q_s:
        out.append(
            _error(
                f"The minimum OA ({cfm(q_min)}) is more than the supply airflow ({cfm(q_s)})."
            )
        )
    if q_b >= q_s:
        out.append(
            _error(
                f"The pressurization bias ({cfm(q_b)}) is not less than the supply airflow ({cfm(q_s)})."
            )
        )
    if a.pressurization_bias.sign == "supply_minus_return" and q_min < q_b:
        out.append(
            _warning(
                f"At minimum OA the relief flow would be negative: the {cfm(q_b)} pressurization bias exceeds "
                f"the {cfm(q_min)} minimum OA, so pressurization is lost at minimum OA."
            )
        )
    return out


def static_checks(cfg: schema.UnitConfig) -> list[Failure]:
    """All checks that need no weather: topology, references, sensor placement,
    coil order, airflow closure, and mode coverage."""
    out = []
    try:
        compile_unit(cfg)
    except ConfigError as e:
        out.append(_error(str(e)))
    out += _sequence_references(cfg)
    out += _sensor_placement(cfg)
    out += _coil_order(cfg)
    out += _airflow_closure(cfg)
    out += mode_coverage(cfg.sequence, site_pressure(cfg.unit))
    return out
