# 0002 — Draft definitions for the §6.1 components that have none

Status: accepted (owner, 2026-10-03). Merged into the schema and `engine/tests/fixtures/example_6_1.json` in M1; all four "choices to confirm" taken as proposed.

The §6.1 lanes name `flt1`, `phc1`, `rhc1`, `sf1`, `rf1`, `ef1` but the
example defines none of them. Per decision 0001, each type's schema model is
added in the M1 ticket that builds its physics (filter and fan: M1-4,
heating coil: M1-5). At that point the approved block below is merged into
`engine/tests/fixtures/example_6_1.json` — a fixture change, so only with
the owner's yes.

## Proposed JSON

```json
"flt1": {"type": "filter",
  "dp_clean": {"value": 0.35, "unit": "in_wc"},
  "dp_dirty": {"value": 1.0, "unit": "in_wc"}},

"phc1": {"type": "heating_coil_hw", "face_area": {"value": 22, "unit": "ft2"},
  "max_face_velocity": {"value": 500, "unit": "fpm"},
  "rating": {"eat": {"value": 40, "unit": "F"}, "lat": {"value": 90, "unit": "F"},
             "airflow": {"value": 10000, "unit": "cfm"},
             "ewt": {"value": 180, "unit": "F"}, "lwt": {"value": 160, "unit": "F"}}},

"rhc1": {"type": "heating_coil_hw", "face_area": {"value": 22, "unit": "ft2"},
  "max_face_velocity": {"value": 500, "unit": "fpm"},
  "rating": {"eat": {"value": 55, "unit": "F"}, "lat": {"value": 75, "unit": "F"},
             "airflow": {"value": 10000, "unit": "cfm"},
             "ewt": {"value": 180, "unit": "F"}, "lwt": {"value": 160, "unit": "F"}}},

"sf1": {"type": "fan", "design_airflow": {"value": 10000, "unit": "cfm"},
  "total_static": {"value": 4.0, "unit": "in_wc"},
  "eta_fan": 0.65, "eta_motor": 0.92, "motor_in_airstream": true},

"rf1": {"type": "fan", "design_airflow": {"value": 9800, "unit": "cfm"},
  "total_static": {"value": 1.5, "unit": "in_wc"},
  "eta_fan": 0.60, "eta_motor": 0.92, "motor_in_airstream": true},

"ef1": {"type": "fan", "design_airflow": {"value": 9800, "unit": "cfm"},
  "total_static": {"value": 1.0, "unit": "in_wc"},
  "eta_fan": 0.60, "eta_motor": 0.92, "motor_in_airstream": true}
```

## Why these numbers

| id | Basis |
| --- | --- |
| `flt1` | MERV 13 bank: ~0.35 in. w.c. clean, 1.0 in. w.c. final (change-out). |
| `phc1` | Exactly the F-10 heating coil (§10.2): 40 → 90 °F at 10,000 cfm, 180/160 °F water. Same 22 ft² face as `cc1` (455 fpm). |
| `rhc1` | Reheat after the cooling coil: 55 → 75 °F at 10,000 cfm, same water. |
| both HW coils | `max_face_velocity` 500 fpm (owner decision 2026-10-03 to add the field; 500 fpm is a common design ceiling, and it sits downstream of the wet cooling coil for `rhc1`). Actual: 10,000 / 22 = 455 fpm. |
| `sf1` | Same ΔP and fan η as F-8 (4.0 in. w.c., 0.65). Motor in airstream (plenum/fan-array) — F-8 tests the other case. |
| `rf1` | Carries all return air: supply − bias = 10,000 − 200 = 9,800 cfm. |
| `ef1` | Carries relief = OA − bias; sized for full economizer: 9,800 cfm. |

## Choices to confirm

1. **Heating-coil rating uses LWT, not GPM.** §5.4 says "LWT or GPM". With
   LWT the water flow follows from the energy balance. Supporting GPM too
   means an either/or field; I propose LWT only for v1.
2. **No `role` field on fans or coils** (supply/return/exhaust, preheat/
   reheat). The lane position already says it. Add one only if the UI or the
   export needs a label the id doesn't give.
3. **Fan `design_airflow` has no `at` location.** It's only compared with the
   solved airflow for the "above design" check, so it is taken at the fan.
4. **Filter ΔP choice.** Which ΔP feeds fan heat — clean, dirty, or a
   per-scenario choice? Proposal: dirty (worst case for SAT after a draw-
   through fan), with clean as an option later.

## Spec issue found while drafting (affects F-12, M2-4)

F-12 says warmup puts 10,000 cfm through the 4.5 ft² RA damper (≈ 2,220
fpm). With OA closed, supply = recirculated air, but return =
supply − 200 cfm bias = 9,800 cfm. Both cannot hold. Either the bias is
lost in warmup (10,000 cfm → 2,222 fpm) or supply drops to 9,800 cfm
(→ 2,178 fpm). Both exceed 1,500 fpm, so F-12 still fails as intended; only
the number in the message changes. Also, warmup fixes `oa_fraction = 0.0`,
below the `min_oa … 1.0` range in §5.4 — I read that as "a mode's fixed
position overrides the minimum". Both to be settled before M2-4.
