# 0005 — M2 controls: decisions, deviations and the failure-message review

Status: made during M2 under CLAUDE.md rules 7 and 9 (decide, record, flag ⚑).
The M2 gate asks the owner to review ten failure messages: see the table at
the end (regenerate with `cd engine && python examples/failure_messages.py`).

## Review first

1. **⚑ F-12 is 2,113 fpm, not ≈ 2,220.** The spec's figure is 10,000 cfm /
   4.5 ft², taking the 10,000 cfm at the damper. The 10,000 cfm is stated at
   the supply-fan discharge (90 °F in warmup); the recirculated air at the
   return damper is ~63 °F and denser, so the same mass is ~9,500 cfm there.
   The test accepts 2,050–2,250 fpm and checks the message names `mix1.ra`.
2. **⚑ The declared `direct`/`reverse` action is not used to judge the loop.**
   The staged solve finds the direction numerically (spec §5.6). A sign check
   against the declared action would give false alarms: an economizer damper
   cools when OA is colder than RA and heats when it is warmer. `action` is kept
   for the sequence export (M6).
3. **⚑ A mode that fixes the OA damper does not report low OA or lost
   pressurization.** Warmup closes OA on purpose; those are consequences of the
   sequence, not faults to chase. Fan, damper velocity, frost etc. still report.
4. **⚑ Fighting = heat upstream of an active cooling coil**, or an economizer
   above minimum with h_OA > h_RA (when a loop, not a fixed position, opened it).
   Cooling plus downstream reheat is dehumidification and is not flagged.
5. **⚑ Coverage only tests schedule values that the conditions name.** The §6.1
   example names only `pre_occupancy`, so `occupied` is never checked. The M4
   weekly schedule will supply the full list.

## Controls model

- Actuator defaults when neither fixed nor driven by an active loop: valves and
  outputs 0; OA damper at the minimum-OA position; wheels running (speed 1,
  bypass 0). Off ends for staging: valves/outputs 0, OA damper at minimum OA,
  wheel speed 0, bypass 1.
- Minimum-OA position: searched so that 3,000 cfm is met *at the OA damper*
  (after the wheel), recomputed each loop pass.
- Staged solve per spec §5.6: 5-point sign check, bisect to 0.01 K, park at the
  nearer end, `SETPOINT_NOT_MET` with last stage, position, PV and shortfall.
  Loop passes repeat until no actuator moves > 0.001 (max 20).
- `space_t` in conditions defaults to the RA dry bulb when not given.
- Btu/lb thresholds compare with I-P enthalpy (exact), not a converted value.
- Overlap is reported only where the tied priority is the one that wins.
- Off-grid condition variables (RA, space) are tested just below, at and above
  each threshold the sequence uses — exact for constant comparisons.

## Schema changes

- `Comparison`: a schedule compares with `==` only.
- `Loop.role` (optional: `preheat`, `freeze_protection`) for the coil-order check.
- `OperatingCondition` for scenario runs (OA db + wb or RH, RA db + RH,
  schedule, optional space_t).
- `Failure.severity` (`error` / `warning`); static checks warn on a single-point
  mixed-air sensor and on negative relief at minimum OA. Only errors block a run.

## Messages

One sentence, I-P (owner works in I-P); `value` / `limit` stay SI so a UI can
show either system. Damper failures name the damper (`mix1.ra`).

## Failure messages for review

| # | Case | Kind | Severity | Message |
| --- | --- | --- | --- | --- |
| 1 | Summer design, cooling loop (F-16) | `setpoint_not_met` | error | Loop sat_cooling cannot hold SAT at 55.0 °F: with cc1.valve at 100 % SAT is 57.8 °F, 2.8 °F above setpoint. |
| 2 | Summer design, minimum OA | `limit_exceeded` | error | The return damper mix1.ra runs at 1,646 fpm, above its 1,500 fpm maximum. |
| 3 | Winter warmup, OA closed (F-12) | `limit_exceeded` | error | The return damper mix1.ra runs at 2,113 fpm, above its 1,500 fpm maximum. |
| 4 | 12,000 cfm supply | `limit_exceeded` | error | Cooling coil cc1 has a face velocity of 567 fpm, above its 500 fpm maximum. |
| 5 | 12,000 cfm supply | `limit_exceeded` | error | Fan sf1 moves 11,930 cfm, above its 10,000 cfm design airflow. |
| 6 | Wheel with no latent recovery, 5 °F OA | `limit_exceeded` | error | Exhaust air leaving erw1 would be 23.0 °F and saturated, so erw1 will frost. |
| 7 | Preheat fixed open while cooling | `fighting` | error | phc1 heats (40 % open) upstream of cc1, which is cooling (60 % open), so the two fight each other. |
| 8 | Economizer used to warm supply air on a humid day | `fighting` | error | Economizer mix1 is open to 72 % (minimum 30 %) while outdoor air at 37.4 Btu/lb carries more enthalpy than return air at 28.1 Btu/lb. |
| 9 | OA damper at 15 % | `limit_exceeded` | error | Outdoor air at mix1 is 1,559 cfm, below the 3,000 cfm minimum. |
| 10 | F-14 sequence | `mode_gap` | error | No mode is active for OA 86 to 113 °F at 10–100 % RH. |
| 11 | F-14 sequence | `mode_overlap` | error | Modes heating and cooling (both priority 1) are both active for OA 48 to 52 °F at 10–100 % RH. |
| 12 | Loop names a missing coil (F-15) | `config_error` | error | Loop sat_heating names phc1.valve, but there is no component phc1. |
| 13 | Single-point MAT sensor | `config_error` | warning | Mixed-air sensor MAT is a single-point temperature sensor; mixed air stratifies, so use an averaging sensor. |
| 14 | Wording only, for a stage whose effect reverses | `non_monotonic` | error | Loop sat_cooling: SAT does not move steadily one way as mix1.oa_fraction strokes, so no single position can be trusted to hold setpoint. |
