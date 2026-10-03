# 0004 — M1 engine: model choices, assumptions and spec deviations

Status: made during M1 under the owner's instruction (2026-10-03) to proceed
without waiting for approval; listed here for review. Items marked **⚑** differ
from the spec text or need the owner's eye.

## Review first

1. **⚑ F-13 does not frost.** Spec §10.2 expects frost for OA −15 °C / 70 %,
   RA 22 °C / 30 %, ε 0.75 / 0.65. With the spec's own model and criterion
   (§5.4: exhaust leaving < 0 °C *and* beyond saturation) the exhaust leaves at
   −5.6 °C and 93 % RH: no frost. ASHRAE's frost-threshold line method agrees
   (the RA→OA line does not cross saturation). An enthalpy wheel returns
   moisture to the supply, which keeps its exhaust unsaturated; a sensible-only
   exchanger at the same conditions does frost, and the tests show both. The
   test encodes the computed result, marked pending owner review, as §10.2 says
   F-13 values are produced by the implementation then reviewed.
2. **⚑ Wheel effectiveness when supply exceeds exhaust.** The spec formula
   T_s,out = T_oa + ε·(T_ex − T_oa) is used as written when m_s ≤ m_e. When
   m_s > m_e, ε is applied to the smaller flow (AHRI 1060 definition);
   otherwise the exhaust side would pass 100 % effectiveness at large ratios
   (second-law violation). F-11 at 1.07 uses this.
3. **⚑ Solver pass limit.** Spec §4 allows ≤ 5 passes for the airflow
   iteration. The solver relaxes states and flows together across both lanes;
   winter wheel cases need ~9 sweeps (each shrinks the change ~4–5×). Cap: 30.
4. **⚑ Fixed-ADP coil capacity.** See `coil-model.md`: at 95/78 °F entering,
   cc1 "delivers" 64.5 tons on a 32-ton rating. `chwr_implied` exposes it.
5. **⚑ The §6.1 unit cannot hold 55 °F SAT at summer design** (57.8 °F with
   the valve open: draw-through fan heat after a coil rated for 55 °F), and its
   4.5 ft² RA damper exceeds 1,500 fpm at minimum OA (1,646 fpm), not only in
   warmup. Design findings, not bugs — see `engine/examples/default_unit.ipynb`.
6. **⚑ Open question §14-2 decided:** the space node exists and works, but the
   §6.1 default config has none (fixed RA).

## Properties and units

- PsychroLib is loaded twice (an SI copy and an I-P copy) instead of toggling
  its global unit system — safe under concurrent API requests.
- Enthalpy thresholds entered in Btu/lb convert with the datum offset
  (0 °F dry air = −17.884 kJ/kg): exact for dry air, within 0.03 Btu/lb for
  moist air. Displayed I-P enthalpy always comes from I-P equations.
- 1 in. w.c. = 249.0889 Pa (water at 39.2 °F); F-8's 996.4 Pa matches.
- A supersaturated state is never created silently: constructors refuse it;
  processes cap at saturation **at constant enthalpy** (fog/frost, which warms
  the air slightly) and report the condensate. Condensate carries zero
  enthalpy everywhere (error < 0.1 % of stream energy), which keeps every
  energy balance exact.
- Checks pass within 0.01 % of their limit, so a value a search lands on
  the limit is not failed by round-off.

## Components

| Component | Choice |
| --- | --- |
| Mixing box | `oa_fraction` = OA share of mixed airflow **by volume at the damper states**, converted to mass fraction (F-7). If OA < pressurization bias, return rises to match, relief = 0 and the `pressurization_bias` check fails; F-12 is then 10,000 cfm basis (resolves the 0002 closure issue). Optional `freeze_threshold`. The box takes `m_supply`/`m_return` from the solver (deviation from the §5.2 signature). |
| Fan | Δh = ΔP·v_in/η per kg dry air, T from PsychroLib (F-8 needs moist-air c_p; dry c_p gives 1.253 K, outside tolerance). `total_static` excludes filters. |
| Filter | Dirty ΔP added to the nearest fan downstream in its lane (else upstream). |
| HW coil | Rating air 50 % RH at EAT (rating gives none; < 0.2 % on UA). Rating at site pressure. UA constant off-design. Valve linear in output (spec). |
| Electric heater | Modulating, or N equal stages: stage k on when output ≥ k/N. |
| CHW coil, design | Spec ADP/BF model. ADP shifts with CHWS; the unit solve uses rated CHWS (no CHWS input in v1). Part valve: h and W both linear in valve (spec says enthalpy; W linear too is my assumption). Optional `max_face_velocity`. |
| CHW coil, measured | Forced leaving db + RH; implied ADP/BF are NaN for a dry or non-cooling coil. |
| Energy wheel | Speed scales ε linearly (spec assumption). Defaults: speed 1, bypass 0. EATR = equal-mass swap at the inlets (energy-conserving); purge has no separate effect (EATR is taken to include it). |
| Sensible HX | Plate / runaround / heat pipe share one model; optional face-velocity pair. |
| Steam humidifier | Isothermal; capped at saturation (`saturation` check). Absorption-distance check is a static check (M2-5). |
| Adiabatic humidifier | Constant h toward wet bulb; capped by max rate (`rate` check). |
| Desiccant wheel | **Low-confidence placeholder**: W_out = W_in·(1 − u·ε_lat); process air gains the regeneration heat; regen side takes the water at constant h. Replace when a real use case appears. |
| Space | Latent heat → moisture via vapor enthalpy from PsychroLib; exfiltration leaves at room state; optional t_min / t_max / rh_max. |

## Lanes and solver

- Supply lane starts at `oa` and ends at a fan; return lane starts at `ra` and
  ends at a fan or at the mixing box (relief). Every component must be placed;
  cross-lane parts once per lane; one mixing box; one space node (not in a lane).
- Return airflow = supply ∓ bias, by volume, converted at the RA state.
- `min_oa` is taken at the OA damper (the only location it is used).
- State keys: `oa_intake`, `ra`, `after:<lane token>`; the mixing box's return
  side is `after:mix1.relief`.
- Converged when every state moves < 1e-4 K and < 1e-8 kg/kg and every flow
  < 1e-6 relative between sweeps.

## Dependencies added

Dev only, to execute the example notebook in tests: nbformat 5.11.1,
nbclient 0.11.0, ipykernel 7.4.0. NumPy (spec §3) is still unused — scalar
root finding needs none.
