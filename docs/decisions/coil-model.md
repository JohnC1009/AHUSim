# Cooling-coil off-design model (M1-9)

Status: **harness ready, awaiting owner's manufacturer selections.** The BF rule
changes only with owner approval (spec §12, M1-9).

## The model under test (spec §5.4, `components/cooling_coil.py`)

- Calibrate from one rating: ADP = rated entering→leaving line extended to
  saturation; BF = (LAT − ADP)/(EAT − ADP).
- Off-design airflow: BF = BF_rated ^ ((m/m_rated)^−0.2) — from BF = exp(−NTU)
  with NTU ∝ m^−0.2 (air-side coefficient ∝ velocity^0.8).
- Off-design water: ADP shifts one-for-one with CHWS.
- Leaving = ADP + BF·(entering − ADP), on T and W; dry coil if entering dew
  point ≤ ADP.

For the §6.1 cc1 rating: ADP 52.6 °F, BF 0.087, 384 MBH (32.0 tons), SHR 0.70.

## What to send

2–3 selections from the coil's manufacturer software for **this coil geometry
at fixed water flow**, each at a condition away from the rating. Most useful:

| # | Change from rating | Why |
| --- | --- | --- |
| 1 | Airflow 8,000 and 12,000 cfm | tests the BF airflow rule |
| 2 | Entering 95 °F db / 78 °F wb | tests the fixed-ADP assumption at high load |
| 3 | CHWS 42 °F (or 46 °F) | tests the ADP-follows-CHWS rule |

For each point: entering db/wb, airflow, CHWS, leaving db/wb, total MBH.
Copy `engine/tests/fixtures/coil_selections/example_rated_point.json`, fill it
in (I-P units are fine), then run
`cd engine && python examples/compare_coil_selections.py`.

## Proposed acceptance

Leaving db and wb within **±1.0 °F**, total capacity within **±5 %**, at every
point. Tighter than this is beyond what a one-point calibration can promise.

## Expected weakness (my prediction, to be confirmed by the data)

With ADP fixed, the model's capacity rises without limit as entering enthalpy
rises. At 95/78 °F entering the cc1 model gives 64.5 tons — twice its rating —
and the energy balance on the rated water flow implies 68.2 °F CHWR against
56 °F rated. A real coil at fixed water flow sees its ADP float up with load and
delivers far less. Point #2 should show this; the solver already reports
`chwr_implied` so a reader can spot it.

If #2 fails the limits, the fix I would propose (owner decision) is a wet-coil
ε-NTU model on enthalpy potential (Braun–Klein–Mitchell), calibrated from the
same rating plus the rated water flow — the water side then limits capacity.
It needs no new user input beyond what the rating already holds.

## Result

_Paste the table from `compare_coil_selections.py` here when selections arrive._
