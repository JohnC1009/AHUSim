# AHU Sequence Verifier — Software Development Specification

Version 0.2-dev · 2026-10-01 · Derived from *AHU Sequence Verifier — Design Document v0.2*.
This file is written for the implementer (Claude Code). The design document holds the reasoning; this file holds what to build, in what order, and how to prove it works.

---

## 1. What we are building

A multi-user browser application that checks whether an air handling unit, as configured, can execute its sequence of operations across the conditions it will see. For each mode and condition it reports which control loop cannot hold setpoint, which actuator or limit stopped it, and by how much.

It is a **steady-state** tool. No transients, no loop tuning.

### In scope (v1)

- Two-lane AHU configurations (supply lane, return/exhaust lane), components from §5.4.
- Structured sequences: modes, loops, fixed positions, alarms.
- Run types: scenario, sweep, annual (EPW weather file).
- Accounts, organizations, project sharing, versioned runs.
- Export of the sequence to the organization's own `.docx` template.

### Out of scope (v1) — do not build

- Transient simulation, PID tuning, fan curves, surge, duct pressure networks.
- Multi-zone load models (a single optional space node only), multiple interacting AHUs.
- DX, gas-fired heat, sound attenuators.
- Equipment selection.
- TMY2 / TMY3 parsing (EPW only).
- Free-form graph wiring in the UI.

---

## 2. Repository layout

Monorepo:

```
ahu-verifier/
├── CLAUDE.md
├── docs/
│   ├── SPEC.md                 # this file
│   └── decisions/              # one short .md per decision made during build
├── engine/                     # pure Python package, no web or database code
│   ├── pyproject.toml
│   ├── ahuverify/
│   │   ├── __init__.py
│   │   ├── _vendor/psychrolib.py
│   │   ├── units.py            # I-P <-> SI conversions, incl. enthalpy datum
│   │   ├── state.py            # AirState, properties
│   │   ├── schema.py           # Pydantic models (the config contract)
│   │   ├── components/         # one module per component type
│   │   ├── lanes.py            # lanes -> solve order
│   │   ├── solver.py           # single-condition forward solve
│   │   ├── controls.py         # modes, loops, staged root finding
│   │   ├── checks.py           # static checks (no weather needed)
│   │   ├── analysis.py         # scenario, sweep, annual
│   │   ├── weather.py          # EPW parser, design days
│   │   └── failures.py         # failure types
│   └── tests/
│       ├── fixtures/           # JSON configs used by tests
│       └── test_*.py
├── api/                        # FastAPI app (from M3)
│   └── app/
├── web/                        # React + TypeScript + Vite app (from M3)
│   └── src/
└── .env.example
```

`engine/` must import nothing from `api/` or `web/`, and must stay pure Python + NumPy (+ Pydantic) so it can later run in the browser via Pyodide.

---

## 3. Stack

| Layer | Choice | Notes |
| --- | --- | --- |
| Engine | Python 3.12, NumPy, Pydantic v2 | PsychroLib vendored as a single file (its pip build can fail; vendoring avoids that) |
| Tests | pytest, ruff | |
| API | FastAPI + Uvicorn, in a container (Fly.io, Render or Railway — owner chooses at M3) | |
| Web | React + TypeScript + Vite | |
| Schematic | React Flow (`@xyflow/react`) with custom nodes | Lane-constrained, no free wiring |
| Psych chart | Custom SVG + `d3-scale` | No Plotly |
| Tables | TanStack Table | |
| Client state | Zustand | |
| Auth | Clerk (sign-in, organizations) | |
| Database | Postgres on Neon, accessed only by the API (SQLAlchemy 2 + Alembic) | No direct browser access |
| Files | Cloudflare R2 (S3 API via `boto3`) | EPW uploads, `.docx` templates |
| Word export | `docxtpl` | Jinja tags inside the org's template |
| Hosting (web) | Vercel | |
| UI tests | Playwright | Smoke tests only |

**Not used:** Supabase (owner decision), Streamlit/Dash, Plotly, any client-side physics.

Pin exact versions in `pyproject.toml` / `package-lock.json` at setup; do not upgrade major versions without asking.

---

## 4. Units and conventions

- Internal: °C, kg/kg dry air, kJ/kg dry air, m³/kg dry air, Pa, kg/s dry air, W.
- Every user-entered quantity in the schema carries its unit: `{"value": 10000, "unit": "cfm"}`. Convert at the schema boundary (`units.py`). Supported input units: listed per field in `schema.py`.
- I-P display of enthalpy: compute with PsychroLib in IP mode from T(°F) and W, i.e. h = 0.240·T + W·(1061 + 0.444·T) Btu/lb. Never `h_SI / 2.326`.
- Volumetric flows carry the location where they apply (`"at": "supply_fan_discharge"`). Convert to dry-air mass flow using the state at that location; where that state depends on the solve, iterate (≤ 5 passes, tolerance 1e-6 relative).
- Pressure: from altitude (standard atmosphere, negative altitude allowed) or an explicit override in Pa.
- Actuator positions are fractions 0–1 internally, shown as 0–100 %.

---

## 5. Engine

### 5.1 AirState

```python
@dataclass(frozen=True)
class AirState:
    t_db: float          # °C
    w: float             # kg/kg dry air
    p: float             # Pa
    # derived (computed once in __post_init__ via PsychroLib, stored as fields):
    h: float             # kJ/kg dry air  (note: PsychroLib returns J/kg; divide by 1000)
    v: float             # m3/kg dry air
    rh: float            # 0–1
    t_dp: float          # °C
    t_wb: float          # °C (PsychroLib handles ice bulb below 0 °C)
```

Constructors: `from_db_rh`, `from_db_w`, `from_db_wb`, `from_db_dp`, `from_h_w`. If a requested state is supersaturated, cap at saturation and return the excess water as `condensate` (kg/kg) on the result of the process that produced it — never silently.

`AirStream = (state: AirState, m_da: float)` with `m_da` in kg/s.

### 5.2 Component interface

Every component module implements:

```python
class Component(Protocol):
    type: str
    def solve(self, inlets: dict[str, AirStream], actuators: dict[str, float],
              p: float) -> ComponentResult: ...

@dataclass
class ComponentResult:
    outlets: dict[str, AirStream]
    loads: dict[str, float]        # W, e.g. q_total, q_sens, q_lat; kg/s for water
    checks: list[Check]            # limit checks with value, limit, pass/fail
    residuals: dict[str, float]    # relative mass/water/energy closure
```

Single-lane components have ports `in`/`out`. Cross-lane components have `supply_in`, `supply_out`, `exhaust_in`, `exhaust_out`. The mixing box has `oa`, `ra`, `mixed`, `relief`.

### 5.3 Residuals

For every component: dry-air mass, water mass (including condensate and steam added) and energy (including coil/fan heat) must close to < 0.1 % relative. Above that, the run is marked `invalid` with an `ENGINE_RESIDUAL` failure. Tests assert residuals for every component.

### 5.4 Components (v1)

| type | Parameters | Actuators | Model | Checks |
| --- | --- | --- | --- | --- |
| `mixing_box` | free area + max face velocity for `oa`, `ra`, `relief` dampers; `min_oa` flow | `oa_fraction` (min_oa … 1.0) | Mass-weighted mix of T via enthalpy and W. Relief flow = OA flow − pressurization bias (sign stated in schema). | Face velocity per damper; OA below min; mixed T below freeze threshold |
| `filter` | clean/dirty ΔP | — | No state change; ΔP feeds fan heat | — |
| `heating_coil_hw` (also used for preheat, reheat) | rating: EAT, LAT, airflow, EWT, LWT or GPM; face area | `valve` (0–1) | UA from rating via ε-NTU (cross-flow, both fluids unmixed; document the correlation used). At valve = 1: max output = ε·C_min·(EWT − EAT). Valve maps linearly to output fraction (assumption, record in `docs/decisions/`). Constant W. | Setpoint reach (via controls); face velocity |
| `electric_heater` | kW, stages | `output` (0–1, stepped if staged) | Sensible, constant W | Capacity |
| `cooling_coil_chw` mode `design` | rating: EAT db/wb, LAT db/wb, airflow, CHWS, CHWR; face area | `valve` (0–1) | From rating derive ADP and bypass factor BF. Leaving = ADP + BF·(entering − ADP) on T and W, where ADP is on saturation. At other conditions: ADP shifts by (CHWS − CHWS_rated); BF adjusted for airflow from BF = exp(−NTU) with NTU ∝ m^−0.2 (air-side coefficient ∝ velocity^0.8), i.e. BF = BF_rated^((m/m_rated)^−0.2) — **assumption to be validated in M1 (ticket M1-9); record in `docs/decisions/`**. Valve < 1 interpolates enthalpy removal linearly between 0 and the valve-open result. If entering dew point ≤ ADP: sensible only. | Setpoint reach; face velocity |
| `cooling_coil_chw` mode `measured` | leaving db + RH | — | Forced leaving state; back-calculates implied ADP, BF, loads, SHR | Leaving state not reachable from entering (W rises, or h rises) |
| `steam_humidifier` | max kg/h, absorption distance | `output` (0–1) | Isothermal; W raised toward target, capped by max rate and saturation | Rate; downstream sensor within absorption distance |
| `adiabatic_humidifier` | effectiveness, max rate | `output` (0–1) | Toward wet bulb at constant h | Rate |
| `energy_wheel` | ε_sens, ε_lat at rating, purge, EATR (0–0.05) | `bypass` (0–1), `speed` (0–1) | Supply: T = T_oa + ε_s·(T_ex,in − T_oa); W likewise with ε_l. Exhaust side by energy/water balance using m_supply/m_exhaust. Speed scales ε linearly (assumption, record). Bypass blends unwheeled air by mass. EATR adds that fraction of exhaust-in air to supply. | Frost: exhaust leaving T < 0 °C **and** exhaust leaving would exceed saturation; residual |
| `plate_hx`, `runaround`, `heat_pipe` | ε_sens at rating | `bypass` | Sensible only, same mass-ratio treatment | Frost; face velocity |
| `desiccant_wheel` | latent ε, regeneration heat (W) | `output` | Black box: latent transfer with sensible penalty equal to regeneration heat; no drying without regen heat | Regen heat unavailable |
| `fan` (supply/return/exhaust) | design airflow, total static ΔP, fan η, motor η, motor in airstream (bool) | — (airflow fixed per mode in v1) | ΔT = ΔP / (ρ·c_p·η_fan) (÷ η_motor too if motor in airstream); W constant | Airflow above design |
| `space` (optional) | sensible W, latent W (or kg/s moisture), or fixed RA state | — | Closes the loop: RA computed from supply + loads | Space T or RH out of the stated range |

### 5.5 Lanes and solve order (`lanes.py`, `solver.py`)

- Config gives two ordered lists of component ports (see §7). Compile to a directed graph.
- Without a `space` node the graph is acyclic: solve in topological order, return lane first up to any cross-lane component's exhaust inlet, then supply.
- With a `space` node: guess RA = space setpoint, solve, update RA, repeat until |ΔT| < 0.01 K and |ΔW| < 1e-6, max 20 passes; else `NON_CONVERGED` failure.
- Validation at compile time (raise `ConfigError` with a plain-English message): one mixing box max; a cross-lane component must appear in both lanes; every lane starts at a boundary (`oa` or `ra`) and ends at a fan or outlet; 100 % OA unit has no mixing box.

### 5.6 Controls (`controls.py`)

**Mode selection.** Modes are evaluated in ascending `priority` number; the first whose `enter` condition is true is active. Conditions are structured data:

```json
{"all": [
  {"var": "schedule", "op": "==", "value": "pre_occupancy"},
  {"var": "space_t", "op": "<", "value": {"value": 68, "unit": "F"}}
]}
```

Supported `var`: `oa_db`, `oa_h`, `oa_dp`, `ra_db`, `ra_h`, `space_t`, `schedule`. Ops: `<`, `<=`, `>`, `>=`, `==`. Combinators: `all`, `any`, `not`. No string expressions, no `eval`.

Static mode checks (`checks.py`): over a grid of OA db −30…45 °C step 1 K × OA RH 10…100 % step 10 % × each schedule value, report `MODE_GAP` (no mode active) and `MODE_OVERLAP` (two modes at equal priority both true).

**Fixed positions.** Applied before loops, from the mode's `fixed` map (`"mix1.oa_fraction": 0.0`).

**Loops.** Each loop: `sensor` (a sensor id on the schematic), `setpoint` (value or reset schedule), `stages` (ordered list of actuator refs, each with `action: "direct" | "reverse"`).

Staged solve for one loop:

1. Hold all stages at their "off" end.
2. For stage i: evaluate the sensed value at the actuator's two ends. If the setpoint lies between them, bisect (tolerance 0.01 K or 1e-6 kg/kg, max 60 iterations) and stop. Otherwise park stage i at the end nearer the setpoint and continue to stage i+1.
3. If every stage is parked and the setpoint is not met: `SETPOINT_NOT_MET` with the loop, last stage, its position, the sensed value, the setpoint and the shortfall.
4. If the sensed value is not monotonic in the actuator (sign check at 5 points fails), raise `NON_MONOTONIC` — do not guess.

Loops are solved in the declared order. Repeat the full loop pass until no actuator moves by more than 0.001, max 20 passes; else `NON_CONVERGED`.

### 5.7 Failures (`failures.py`)

```python
class FailureKind(StrEnum):
    SETPOINT_NOT_MET = "setpoint_not_met"
    LIMIT_EXCEEDED = "limit_exceeded"       # face velocity, rate, frost
    MODE_GAP = "mode_gap"
    MODE_OVERLAP = "mode_overlap"
    CONFIG_ERROR = "config_error"           # missing sensor/actuator, bad topology
    FIGHTING = "fighting"                   # simultaneous heat+cool; economizer with h_oa > h_ra
    CANNOT_COMPUTE = "cannot_compute"       # required input missing
    NON_MONOTONIC = "non_monotonic"
    NON_CONVERGED = "non_converged"
    ENGINE_RESIDUAL = "engine_residual"
```

Every failure carries: `kind`, `mode`, `condition_id`, `component` (or loop), `message` (one plain-English sentence with numbers and units), `value`, `limit`.

### 5.8 Static checks (`checks.py`)

Run on every config/sequence change, no weather:

- Every loop sensor exists; every actuator a sequence names exists.
- Coil order vs sequence: a loop declared as preheat/freeze protection must act on a heating coil upstream of the cooling coil.
- Sensor placement: humidity sensor within a humidifier's absorption distance; mixed-air temperature sensor not of averaging type → warning.
- Airflow closure: supply = OA + recirculated; return = recirculated + relief; pressurization bias sign stated.

### 5.9 Analysis (`analysis.py`, `weather.py`)

| Run | Input | Output |
| --- | --- | --- |
| `scenario` | list of named conditions | per condition: mode, states, actuator positions, loads, checks, failures |
| `sweep` | 1 or 2 variables with ranges; max 50 × 50 | grid of pass/fail + failure kind |
| `annual` | EPW file + weekly schedule | hours per mode; hours failed per mode × failure kind; bin table OA db (2 K) × coincident W (1 g/kg); optional hourly CSV |

`annual` refuses to run (`CANNOT_COMPUTE`) if any coil lacks a rating or any wheel lacks frost parameters.

EPW parser: read the 8 header lines and 8760 data rows; use dry bulb, dew point, RH and station pressure. Validate row count; leap-year files are allowed to have 8784 rows.

---

## 6. Schema (`schema.py`)

Pydantic v2 models are the contract. Generate JSON Schema from them (`ahuverify.schema.export_json_schema()`), and generate TypeScript types from that JSON Schema for `web/` (`json-schema-to-typescript`). Bump `schema_version` on any breaking change and write a migration function.

### 6.1 Example config

```json
{
  "schema_version": "0.2",
  "unit": {"name": "AHU-1", "altitude": {"value": 33, "unit": "ft"}, "pressure_override": null},
  "airflows": {
    "supply": {"value": 10000, "unit": "cfm", "at": "supply_fan_discharge"},
    "min_oa": {"value": 3000, "unit": "cfm", "at": "oa_damper"},
    "pressurization_bias": {"value": 200, "unit": "cfm", "sign": "supply_minus_return"}
  },
  "lanes": {
    "supply": ["oa", "erw1.supply", "mix1", "flt1", "phc1", "cc1", "rhc1", "sf1"],
    "return": ["ra", "rf1", "mix1", "erw1.exhaust", "ef1"]
  },
  "components": {
    "mix1": {"type": "mixing_box",
      "dampers": {"oa": {"free_area": {"value": 8.0, "unit": "ft2"}, "max_velocity": {"value": 1500, "unit": "fpm"}},
                  "ra": {"free_area": {"value": 4.5, "unit": "ft2"}, "max_velocity": {"value": 1500, "unit": "fpm"}},
                  "relief": {"free_area": {"value": 6.0, "unit": "ft2"}, "max_velocity": {"value": 1500, "unit": "fpm"}}}},
    "cc1": {"type": "cooling_coil_chw", "mode": "design", "face_area": {"value": 22, "unit": "ft2"},
      "rating": {"eat_db": {"value": 80.5, "unit": "F"}, "eat_wb": {"value": 67.0, "unit": "F"},
                 "lat_db": {"value": 55.0, "unit": "F"}, "lat_wb": {"value": 54.0, "unit": "F"},
                 "airflow": {"value": 10000, "unit": "cfm"},
                 "chws": {"value": 44, "unit": "F"}, "chwr": {"value": 56, "unit": "F"}}},
    "erw1": {"type": "energy_wheel", "eps_sens": 0.75, "eps_lat": 0.65, "purge": true, "eatr": 0.02}
  },
  "sensors": [
    {"id": "SAT", "type": "temperature", "at": "after:sf1"},
    {"id": "MAT", "type": "temperature_averaging", "at": "after:mix1"}
  ],
  "sequence": {
    "modes": [
      {"id": "warmup", "priority": 2,
       "enter": {"all": [{"var": "schedule", "op": "==", "value": "pre_occupancy"},
                         {"var": "space_t", "op": "<", "value": {"value": 68, "unit": "F"}}]},
       "fixed": {"mix1.oa_fraction": 0.0, "cc1.valve": 0.0},
       "loops": ["sat_heating"]}
    ],
    "loops": {
      "sat_heating": {"sensor": "SAT", "setpoint": {"value": 90, "unit": "F"},
                      "stages": [{"actuator": "phc1.valve", "action": "direct"}]}
    }
  },
  "conditions": {"weather_file": "USA_NY_New.York-Central.Park.epw",
                 "scenarios": ["summer_design", "winter_design"]}
}
```

Numbers are placeholders for shape. Note: in this example the warmup mode puts 10,000 cfm through a 4.5 ft² return damper (≈ 2,220 fpm vs 1,500 fpm max) — it is used as fixture F-12.

### 6.2 Run record

`Run = {config_hash, sequence_hash, conditions_hash, engine_version, created_at, results, failures, valid: bool}`. Results are reproducible from the hashes + engine version.

---

## 7. API (from M3)

All endpoints require a Clerk session token (verified server-side with Clerk's JWKS). All project access checks happen in the API.

| Method | Path | Body / query | Returns |
| --- | --- | --- | --- |
| POST | `/v1/solve` | config + one condition | single-condition result |
| POST | `/v1/scenario` | config + scenario list | scenario results |
| POST | `/v1/sweep` | config + sweep spec | grid |
| POST | `/v1/annual` | config + weather ref + schedule | annual summary (+ CSV link) |
| POST | `/v1/checks` | config | static check results |
| GET/POST/PATCH/DELETE | `/v1/projects…` | — | projects, units, versions |
| POST | `/v1/projects/{id}/members` | user, role | membership |
| POST | `/v1/export/docx` | unit version + template ref | file link |
| GET | `/v1/projects/{id}/export` | — | full project JSON |

Limits per user (configurable): annual runs 30/hour, sweep ≤ 2,500 points. Return 429 with a plain message when exceeded.

### 7.1 Database tables (Postgres on Neon)

`users` (Clerk id), `orgs`, `org_members(role)`, `projects(org_id nullable)`, `project_members(role: owner|editor|reviewer|viewer)`, `units`, `unit_versions(config jsonb, sequence jsonb, conditions jsonb, created_by, created_at)`, `runs`, `files(r2_key, kind: epw|template, owner)`, `audit_log`.

### 7.2 Permissions

| Action | owner | editor | reviewer | viewer |
| --- | --- | --- | --- | --- |
| View, run | ✓ | ✓ | ✓ | ✓ |
| Comment | ✓ | ✓ | ✓ | |
| Edit unit, sequence, conditions | ✓ | ✓ | | |
| Manage members, delete project | ✓ | | | |

One function `require(user, project, action)` enforces this; every route calls it. A parametrized test covers every route × every role (M5 gate).

---

## 8. Web app (from M3)

### 8.1 Pages

`/projects` · `/projects/:id` · `/units/:id` (Unit workspace) · `/units/:id/sequence` · `/units/:id/conditions` · `/units/:id/results` · `/units/:id/export` · `/settings` (profile: unit system, default location, altitude).

### 8.2 Unit workspace

- **Top bar:** project / unit name, **mode + condition selector** (drives every view), Run, I-P/SI toggle.
- **Left:** component palette (only items valid for the selected lane slot are enabled), mode list.
- **Centre:** schematic, supply lane above, return/exhaust lane below, cross-lane components spanning both. Drop into slots; no free wiring. Duct-segment labels switchable db/RH, db/W, h.
- **Right:** inspector for the selected component, damper or sensor.
- **Bottom dock, split and resizable:** psych chart (left) and state table (right). Hovering a state in any of schematic, chart or table highlights it in all three.
- **Failure strip** pinned above the dock: one line per failure; click selects mode, condition and component.
- Parameter edits trigger a debounced (300 ms) `/v1/solve`.

### 8.3 Psych chart

Custom SVG. Saturation curve, db lines, W lines, RH lines (10 % steps), enthalpy lines, wet-bulb lines, all computed **by the API** (`GET /v1/chart-grid?p=…&units=…`) and cached client-side. Process path for the selected mode/condition. Sweep overlay as a pass/fail field coloured by failure kind, with a distinct marker shape per kind.

### 8.4 Design system (M0 deliverable, binding)

`web/src/design/tokens.ts`: type scale, spacing scale (multiples of 4), neutrals, one accent, status colours (pass / warning / fail), radii, schematic symbol set (coil, damper, fan, wheel, humidifier, filter, sensor). Every component uses tokens only — no ad-hoc colours or sizes. Tabular numerals in all tables; units in every column header. Status always shown by colour **and** shape/icon.

Breakpoints: editor ≥ 1280 px; tablet 1024–1279 px edits parameters and views results; < 1024 px read-only results and comments.

---

## 9. Sequence export (M6)

- The organization uploads its 23 09 93 `.docx` template with `docxtpl` Jinja tags.
- Provide a documented context object: `unit`, `modes[]` (name, entry conditions rendered in words, fixed positions, loops), `loops[]`, `alarms[]`, `points[]`.
- Ship one example template in `api/templates/example_230993.docx`.
- Also export Markdown (review) and a points list CSV.

---

## 10. Fixtures and tests

### 10.1 Property fixtures (sea level, 101,325 Pa)

Computed with PsychroLib 2.5.0 on 2026-10-01. Tolerances: W and h ±0.1 %, v ±0.1 %, temperatures ±0.05 K.

| ID | State | W (g/kg) | h (kJ/kg) | v (m³/kg) | T_dp (°C) | T_wb (°C) |
| --- | --- | --- | --- | --- | --- | --- |
| F-1 | 25 °C, 50 % RH | 9.881 | 50.322 | 0.8580 | 13.86 | 17.89 |
| F-2 | 35 °C, 40 % RH | 14.132 | 71.473 | 0.8928 | 19.38 | 23.93 |
| F-3 | 24 °C, 50 % RH | 9.299 | 47.815 | 0.8544 | 12.95 | 17.07 |

| ID | Check | Expected |
| --- | --- | --- |
| F-4 | Saturation pressure at 25 °C / 0 °C | 3,169.2 Pa / 611.2 Pa |
| F-5 | I-P display at 70 °F, 50 % RH | W = 54.48 gr/lb, h = 25.30 Btu/lb (fails if h ≈ 17.6) |
| F-6 | Wet bulb at −10 °C, 80 % RH (ice-bulb branch) | −10.65 °C |

### 10.2 Process and system fixtures

| ID | Case | Expected |
| --- | --- | --- |
| F-7 | Mix F-2 (OA) and F-3 (RA), 30 % OA **by volume** | mass OA fraction 0.2908; T_mix 27.22 °C; W_mix 10.704 g/kg (a volumetric mix would give 27.30 °C / 10.748 g/kg — must not) |
| F-8 | Fan: 4.0 in. w.c. (996.4 Pa), η_fan 0.65, motor outside airstream, air at 13 °C / W 0.009 | ΔT = 1.23 K (2.22 °F) ± 0.02 K |
| F-9 | Cooling coil design mode at its own rating point | reproduces rated LAT db/wb within 0.1 K |
| F-10 | Heating coil at its own rating point; then EAT lowered 10 K at valve 1.0 | reproduces rating within 0.1 K; max output increases |
| F-11 | Energy wheel equal and unequal flows (m_s/m_e = 1.0 and 1.07) | energy and water residual < 0.1 %; exhaust side uses mass ratio |
| F-12 | §6.1 example, warmup mode | `LIMIT_EXCEEDED` on `mix1.ra`, ≈ 2,220 fpm vs 1,500 fpm, message names the damper |
| F-13 | Winter wheel: OA −15 °C / 70 %, RA 22 °C / 30 %, ε 0.75/0.65, no bypass | frost flagged |
| F-14 | Two modes overlapping and an uncovered OA range | one `MODE_OVERLAP` and one `MODE_GAP` |
| F-15 | Loop names `phc1.valve` with no `phc1` in config | `CONFIG_ERROR` before any solve |
| F-16 | Cooling loop on SAT at an OA condition beyond coil capacity | `SETPOINT_NOT_MET`, stage `cc1.valve` at 1.0, shortfall in K |

F-9 and F-10 rating inputs: use the coil in §6.1 and a heating coil rated 40 °F → 90 °F at 10,000 cfm, 180 °F / 160 °F water. F-13 and F-16 expected values are produced by the implementation, then **reviewed and approved by the owner** before they become fixed fixtures.

### 10.3 Other tests

- Schema round-trip: every fixture config → model → JSON → model is identical.
- Unit conversions: each supported unit to SI and back within 1e-9 relative.
- Permissions (M5): every route × every role.
- UI smoke (M3+): Playwright builds the §6.1 unit from a blank project and reaches a summer-design result.

---

## 11. Non-functional

- Single-condition solve ≤ 50 ms engine time for the §6.1 unit.
- Annual run ≤ 5 s engine time.
- All errors shown to users are one plain sentence with numbers and units; stack traces only in logs.
- Disclaimer accepted at sign-up and shown in every export: "Engineering aid only. Not a substitute for PE-reviewed calculations or manufacturer selections."

---

## 12. Milestones and tickets

Work strictly in order. Each milestone ends at its **gate**; the owner confirms the gate before the next milestone starts.

### M0 — Freeze spec and design

- [ ] M0-1 Create repo skeleton per §2; `engine/` installable (`pip install -e engine`); pytest and ruff run (no tests yet).
- [ ] M0-2 Vendor PsychroLib 2.5.0 with its licence file.
- [ ] M0-3 `schema.py` Pydantic models for §6.1; export JSON Schema; round-trip test.
- [ ] M0-4 `web/src/design/tokens.ts` and four static HTML mockups (Unit, Sequence, Results, Export) using only the tokens. No React yet.

**Gate:** owner approves schema and mockups.

### M1 — Engine package

- [ ] M1-1 `units.py` with conversion tests.
- [ ] M1-2 `state.py` AirState + constructors; F-1 … F-6.
- [ ] M1-3 Mixing box (mass basis, damper face velocities); F-7.
- [ ] M1-4 Fan, filter; F-8.
- [ ] M1-5 Heating coil (ε-NTU from rating), electric heater; F-10.
- [ ] M1-6 Cooling coil design + measured modes; F-9.
- [ ] M1-7 Humidifiers, energy wheel, sensible HX family, desiccant wheel; F-11, F-13.
- [ ] M1-8 `lanes.py` + `solver.py` forward solve with residuals; space node iteration.
- [ ] M1-9 Coil off-design validation: owner supplies 2–3 manufacturer selections at off-design conditions; compare; write result to `docs/decisions/coil-model.md`; adjust BF rule only with owner approval.
- [ ] M1-10 Example notebook `engine/examples/default_unit.ipynb` that solves the §6.1 unit at summer and winter design and prints a state table.

**Gate:** all fixtures F-1 … F-11, F-13 pass; M1-9 accepted by owner.

### M2 — Controls layer

- [ ] M2-1 Structured conditions + mode selection.
- [ ] M2-2 Static mode coverage check; F-14.
- [ ] M2-3 Staged loop solver with monotonic check and outer iteration; F-16.
- [ ] M2-4 Failure model and messages; F-12.
- [ ] M2-5 Static configuration checks (§5.8); F-15.
- [ ] M2-6 `analysis.scenario`.

**Gate:** F-12 … F-16 pass; owner reviews ten failure messages for clarity.

### M3 — Web app, single user

- [ ] M3-1 FastAPI app: `/v1/solve`, `/v1/scenario`, `/v1/checks`, `/v1/chart-grid`; Clerk token verification.
- [ ] M3-2 Neon database, Alembic migrations for `users`, `projects`, `units`, `unit_versions`, `runs`; save/load own projects.
- [ ] M3-3 Generated TypeScript types; React app shell with Clerk sign-in.
- [ ] M3-4 Schematic editor (React Flow, lane slots, palette, inspector).
- [ ] M3-5 Psych chart, state table, failure strip, linked highlighting.
- [ ] M3-6 Sequence editor (modes, loops, structured conditions — form based).
- [ ] M3-7 JSON export/import of a unit.
- [ ] M3-8 Deploy: web on Vercel, API container on the host the owner chooses.

**Gate:** a first-time user builds the §6.1 unit from blank and gets a summer-design result in under 10 minutes (owner watches one person try); Playwright smoke test passes.

### M4 — Weather and analysis

- [ ] M4-1 EPW parser + upload to R2; NYC Central Park file as a bundled sample.
- [ ] M4-2 Design-day scenarios (source and licensing per §14-3 decision).
- [ ] M4-3 `sweep` + chart overlay.
- [ ] M4-4 `annual` + bins table + hourly CSV.

**Gate:** annual bin totals reconcile exactly with the hourly CSV; sweep overlay matches spot-checked single solves.

### M5 — Accounts and sharing

- [ ] M5-1 Organizations (Clerk orgs) mirrored in `orgs` / `org_members`.
- [ ] M5-2 Project membership + roles; `require()` on every route.
- [ ] M5-3 Version history and run reproducibility (re-run a stored run, compare).
- [ ] M5-4 Account deletion + project export.
- [ ] M5-5 Rate limits; disclaimer acceptance; terms page.

**Gate:** permission test matrix passes; licensing questions in §14 answered.

### M6 — Sequence documents

- [ ] M6-1 Context object + Markdown export.
- [ ] M6-2 `docxtpl` export with the org template; example template.
- [ ] M6-3 Points list CSV.

**Gate:** one real project sequence round-trips into the firm template and the owner accepts the output.

---

## 13. Decisions already made — do not reopen without the owner

Python engine (not TypeScript); PsychroLib (no hand-written property equations); SI internal; mass basis; lanes (not free graph); sequence is an input (not generated from the diagram); Clerk + Neon + R2 (not Supabase); EPW only; desktop-first UI; steady state only.

## 14. Open questions — stop and ask when you reach them

1. Cooling-coil off-design rule (resolved by M1-9).
2. Space node included in v1 defaults, or fixed RA only?
3. Licensing of ASHRAE design-day values and of any Guideline 36–structured starter sequences on a public site.
4. API host choice (Fly.io, Render, Railway).
5. Free or paid; final rate limits.
6. Whether a free-text → structured sequence importer joins this product.
7. Whether code from the owner's existing `psychro.py` is reused in `engine/`.
