# 0007 — Energy wheel: airflow and speed effectiveness, AHRI 1060 leakage

Status: requested by owner 2026-10-07 ("options 1 and 2, not full physics, with
inputtable leakage"). Supersedes the wheel rows of 0004 where they differ.
All new inputs are optional: a wheel without them behaves as before.

## Model (`engine/ahuverify/components/energy_wheel.py`)

**Effectiveness form** (EnergyPlus `HeatExchanger:AirToAir:SensibleAndLatent`):
supply leaving = OA + ε·(m_min/m_supply)·(RA − OA), on T with ε_s and on W
with ε_L; exhaust side by energy and water balance on dry-air mass.

**1. ε vs airflow.** `eps_sens` / `eps_lat` apply at `rated_airflow`;
`airflow_ratings` add points (e.g. the AHRI 75 % point, or 3–4 selections).
Linear interpolation on the average face airflow ½(Q_supply + Q_exhaust) at the
wheel's inlet states; beyond the outer points the nearest segment is extended
(as EnergyPlus does); ε clamped to 0–1.

**2. ε vs speed** (Kays & London / Lambertson rotary regenerator):
ε(n) = ε_rated · [f(Cr*·n) / f(Cr*)]^k, f(x) = 1 − 1/(9·x^1.93),
Cr* = M·c·(rpm/60) / C_min at rated speed. Inputs: `rated_speed_rpm` and
`matrix_heat_capacity` (Btu/°F or kJ/K). Speed actuator = fraction of rated rpm.
- The factor is applied **relative to rated speed**, so ε at rated speed is
  exactly the selection value; the airflow interpolation sets ε_rated.
- f is clamped at 0 below Cr* ≈ 0.32 (the correlation is not valid there).
- ⚑ **Latent** uses the same factor raised to `latent_speed_exponent` k ≥ 1
  (default 1 = same as sensible). The desiccant saturates sooner at low rpm,
  so k > 1 in practice — **calibrate it** from selections at 2–3 wheel speeds;
  I have no published value to default to.
- Without the two inputs, speed scales ε linearly (previous behaviour).
- Starting value for M·c: matrix weight × 0.215 Btu/lb·°F (aluminium) — the
  matrix is part of the wheel weight; fit against speed selections if you can.

Hand check: at rated Cr* = 10, half speed costs 0.4 % of ε, 10 % speed costs
11 % — wheels only lose effectiveness at low rpm, which is why VFD wheels are
turned down hard for capacity control.

**3. Leakage (AHRI 1060).** `eatr` (exhaust air transfer ratio) and `oacf`
(outdoor air correction factor = OA in / supply out):
- supply out = OA in / OACF
- carryover (exhaust → supply) = EATR · supply out, at the exhaust-inlet state
- purge / seals (OA → exhaust) = (OACF − 1 + EATR) · supply out, at OA state
Leakage air bypasses the exchange and mixes into the leaving streams, so mass,
water and energy close exactly. OACF ≥ 1 − EATR is enforced (no negative purge).
Default OACF = 1.0 (purge equals carryover), matching the old model's flows.
- The SEMCO example (32,919 cfm OA, 30,000 cfm supply, 2,919 cfm purge/seals)
  is OACF = 1.097 — a test case.
- The solver draws OA intake = OACF × the OA the mixing box receives, so the
  intake, wheel and exhaust fans all carry the right flow. ⚑ OACF is applied
  for wheels on the OA path (upstream of the mixing box, or anywhere in the
  supply lane of a 100 % OA unit).
- ⚑ Behaviour change: carryover is now mixed in *after* the exchange (it is
  exhaust-inlet air that never crossed the matrix as supply). In summer this
  pulls the supply toward the return state — slightly drier — where the old
  inlet-swap model happened to make it wetter. §6.1 results are unchanged at
  displayed precision.
- `purge` (bool) stays informational; the purge flow comes from OACF.

**Condensation check (new).** A wheel side leaving beyond saturation at or
above 0 °C fails `condensation` (reported as the highest leaving RH against
100 %); below 0 °C the existing `frost` check applies. Both use the leaving
state before any condensing.

## Diagnostics in every result

`eps_sens`, `eps_lat` (as applied), `m_carryover`, `m_purge`, `condensate`.

## Not done (option 3)

Coupled heat and mass transfer over the matrix with a sorption isotherm needs
matrix mass, desiccant loading and isotherm, and channel geometry that
manufacturers don't publish; it would end up fitted to the same selection data.
