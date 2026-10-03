"""Single-condition forward solve of a compiled unit (spec §5.5).

Given OA and RA states and every actuator position, sweep the return lane
then the supply lane, repeatedly, until all states and flows stop changing.
Cross-lane parts (mixing box, wheels, exchangers) use the latest values from
the other lane, so each sweep refines the coupling. Volumetric airflows are
converted to dry-air mass with the state at their stated location (spec §4):
  supply:  m_s = Q_supply / v at its location (default: supply fan discharge)
  return:  m_r = (Q_supply ∓ Q_bias) / v_RA    (bias sign from the config)
With a space node, RA is recomputed from the supply air each sweep.
"""

from dataclasses import dataclass, field

from ahuverify.components import RESIDUAL_LIMIT, ComponentResult
from ahuverify.components.mixing_box import oa_mass_fraction
from ahuverify.failures import Failure, FailureKind
from ahuverify.lanes import CROSS_LANE, CompiledUnit, ConfigError, Slot
from ahuverify.state import AirState, AirStream

_T_TOL = 1e-4  # K
_W_TOL = 1e-8  # kg/kg
_M_TOL = 1e-6  # relative


@dataclass
class SolveResult:
    states: dict[str, AirStream]  # "oa_intake", "ra", "after:<lane token>"
    components: dict[str, ComponentResult]
    passes: int
    converged: bool
    failures: list[Failure] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not any(
            f.kind in (FailureKind.NON_CONVERGED, FailureKind.ENGINE_RESIDUAL)
            for f in self.failures
        )


@dataclass
class _Flows:
    m_s: float  # supply (mixed) dry-air flow
    m_r: float  # design return flow
    m_oa: float  # OA drawn (equals m_s without a mixing box)
    m_ra: float  # return actually drawn at the mixing box
    m_relief: float


def _actuators_by_component(
    unit: CompiledUnit, actuators: dict[str, float]
) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {name: {} for name in unit.components}
    for ref, value in actuators.items():
        comp, _, act = ref.partition(".")
        if comp not in out or not act:
            raise ConfigError(
                f'Actuator "{ref}" does not name a component in this unit.'
            )
        out[comp][act] = value
    return out


def _return_volume_flow(unit: CompiledUnit) -> float:
    """Return airflow, m³/s: supply minus (or plus) the pressurization bias."""
    a = unit.cfg.airflows
    sign = -1.0 if a.pressurization_bias.sign == "supply_minus_return" else 1.0
    return a.supply.si + sign * a.pressurization_bias.si


def _initial_flows(unit: CompiledUnit, oa: AirState, ra: AirState, acts) -> _Flows:
    # RA is a far better stand-in than OA for the supply-fan discharge state.
    m_s = unit.cfg.airflows.supply.si / ra.v
    m_r = _return_volume_flow(unit) / ra.v
    if unit.mixing_box is None:
        return _Flows(m_s, m_r, m_s, m_r, m_r)
    f = acts[unit.mixing_box].get("oa_fraction", 0.0)
    m_oa = oa_mass_fraction(f, oa.v, ra.v) * m_s
    m_ra = max(m_r, m_s - m_oa)
    return _Flows(m_s, m_r, m_oa, m_ra, m_ra - (m_s - m_oa))


def _segment_flow(
    slots: list[Slot], token: str, unit: CompiledUnit, before: float, after: float
) -> float:
    """Flow at a lane position: `before` upstream of the mixing box, `after` downstream."""
    for s in slots:
        if s.comp == unit.mixing_box:
            return after
        if s.token == token:
            return before
    return before


class _Sweep:
    """One unit, one condition: holds the latest cross-lane inlets between sweeps."""

    def __init__(self, unit: CompiledUnit, oa: AirState, acts):
        self.unit, self.oa, self.acts = unit, oa, acts
        self.cross_supply_in: dict[str, AirStream] = {}
        self.cross_exhaust_in: dict[str, AirStream] = {}
        self.box_oa_in: AirStream | None = None
        self.box_ra_in: AirStream | None = None
        self.results: dict[str, ComponentResult] = {}

    def _solve(self, name: str, inlets: dict[str, AirStream], **kw) -> ComponentResult:
        try:
            r = self.unit.components[name].solve(
                inlets, self.acts[name], self.unit.p, **kw
            )
        except KeyError as missing:
            raise ConfigError(
                f"Actuator {name}.{missing.args[0]} has no position for this solve."
            ) from None
        self.results[name] = r
        return r

    def step(
        self, slot: Slot, cur: AirStream, lane: str, flows: _Flows, ra_state: AirState
    ) -> AirStream:
        u = self.unit
        kind = u.components[slot.comp].type
        if slot.comp == u.mixing_box:
            if lane == "return":
                self.box_ra_in = cur
            else:
                self.box_oa_in = cur
            oa_in = self.box_oa_in or AirStream(self.oa, flows.m_oa)
            ra_in = self.box_ra_in or AirStream(ra_state, flows.m_ra)
            r = self._solve(
                slot.comp,
                {"oa": oa_in, "ra": ra_in},
                m_supply=flows.m_s,
                m_return=flows.m_r,
            )
            return r.outlets["relief" if lane == "return" else "mixed"]
        if kind in CROSS_LANE:
            if lane == "return":
                self.cross_exhaust_in[slot.comp] = cur
            else:
                self.cross_supply_in[slot.comp] = cur
            sup = self.cross_supply_in.get(slot.comp) or AirStream(
                self.oa,
                _segment_flow(
                    u.supply, f"{slot.comp}.supply", u, flows.m_oa, flows.m_s
                ),
            )
            exh = self.cross_exhaust_in.get(slot.comp) or AirStream(
                ra_state,
                _segment_flow(
                    u.return_, f"{slot.comp}.exhaust", u, flows.m_ra, flows.m_relief
                ),
            )
            r = self._solve(slot.comp, {"supply_in": sup, "exhaust_in": exh})
            return r.outlets["exhaust_out" if lane == "return" else "supply_out"]
        return self._solve(slot.comp, {"in": cur}).outlets["out"]


def _state_key(slot: Slot, lane: str, unit: CompiledUnit) -> str:
    if lane == "return" and slot.comp == unit.mixing_box:
        return f"after:{slot.token}.relief"
    return f"after:{slot.token}"


def _snapshot(states: dict[str, AirStream]) -> dict[str, tuple[float, float, float]]:
    return {k: (s.state.t_db, s.state.w, s.m_da) for k, s in states.items()}


def _changed(a: dict, b: dict) -> bool:
    if a.keys() != b.keys():
        return True
    for k, (t, w, m) in a.items():
        t2, w2, m2 = b[k]
        if (
            abs(t - t2) > _T_TOL
            or abs(w - w2) > _W_TOL
            or abs(m - m2) > _M_TOL * max(abs(m2), 1e-12)
        ):
            return True
    return False


def solve(
    unit: CompiledUnit,
    oa: AirState,
    ra: AirState,
    actuators: dict[str, float],
    *,
    max_passes: int | None = None,
) -> SolveResult:
    """Solve one operating condition. RA is the boundary return state (or the
    first guess for it when the unit has a space node)."""
    acts = _actuators_by_component(unit, actuators)
    # Each sweep shrinks the change ~4-5x; winter wheel cases need ~10 sweeps.
    max_passes = max_passes or 30
    flows = _initial_flows(unit, oa, ra, acts)
    sweep = _Sweep(unit, oa, acts)
    ra_state = ra
    previous: dict = {}
    states: dict[str, AirStream] = {}
    for n in range(1, max_passes + 1):
        states = {"ra": AirStream(ra_state, flows.m_ra)}
        cur = states["ra"]
        for slot in unit.return_[1:]:
            cur = sweep.step(slot, cur, "return", flows, ra_state)
            states[_state_key(slot, "return", unit)] = cur
        cur = AirStream(oa, flows.m_oa)
        states["oa_intake"] = cur
        for slot in unit.supply[1:]:
            cur = sweep.step(slot, cur, "supply", flows, ra_state)
            states[_state_key(slot, "supply", unit)] = cur
        if unit.space:
            ra_state = sweep._solve(unit.space, {"in": cur}).outlets["out"].state
        flows = _updated_flows(unit, flows, states, ra_state, sweep.results)
        snap = _snapshot(states) | {"_ra": (ra_state.t_db, ra_state.w, flows.m_s)}
        if previous and not _changed(snap, previous):
            return _finish(states, sweep.results, n, True)
        previous = snap
    return _finish(states, sweep.results, max_passes, False)


def _updated_flows(
    unit: CompiledUnit, flows: _Flows, states, ra_state: AirState, results
) -> _Flows:
    m_s = unit.cfg.airflows.supply.si / states[unit.supply_flow_location].state.v
    m_r = _return_volume_flow(unit) / ra_state.v
    if unit.mixing_box is None:
        return _Flows(m_s, m_r, m_s, m_r, m_r)
    box = results[unit.mixing_box].loads
    return _Flows(m_s, m_r, box["m_oa"], box["m_ra"], box["m_relief"])


def _finish(states, results, passes: int, converged: bool) -> SolveResult:
    failures = []
    if not converged:
        failures.append(
            Failure(
                FailureKind.NON_CONVERGED,
                f"The unit solve did not settle within {passes} passes.",
            )
        )
    for name, r in results.items():
        for quantity, value in r.residuals.items():
            if abs(value) > RESIDUAL_LIMIT:
                failures.append(
                    Failure(
                        FailureKind.ENGINE_RESIDUAL,
                        f"{name} does not close its {quantity.replace('_', ' ')} balance "
                        f"({abs(value) * 100:.3f} % against a 0.1 % limit).",
                        component=name,
                        value=abs(value),
                        limit=RESIDUAL_LIMIT,
                    )
                )
    return SolveResult(states, results, passes, converged, failures)


def oa_damper_flow(unit: CompiledUnit, result: SolveResult) -> float:
    """Volumetric OA flow at the OA damper, m³/s: m_oa × v of the air entering
    the mixing box's OA port (where min OA is stated)."""
    if unit.mixing_box is None:
        return 0.0
    m_oa = result.components[unit.mixing_box].loads["m_oa"]
    tokens = [s.token for s in unit.supply]
    i = next(k for k, s in enumerate(unit.supply) if s.comp == unit.mixing_box)
    key = "oa_intake" if i == 1 else f"after:{tokens[i - 1]}"
    return m_oa * result.states[key].state.v
