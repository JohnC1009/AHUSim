# 0001 — M0 schema scope and setup choices

Status: accepted by owner 2026-10-02 (option 1: schema covers §6.1 now;
each component's model is added in the M1 ticket that builds its physics,
with the owner approving its fields)

- `schema.py` models only what the §6.1 example uses: component types
  `mixing_box`, `cooling_coil_chw` (mode `design` only), `energy_wheel`;
  sensor types `temperature`, `temperature_averaging`; loop setpoints as a
  fixed temperature. Other §5.4 components, measured coil mode, humidity
  sensors, reset schedules and alarms are added when their tickets arrive.
- Quantities are stored as entered (`{"value", "unit"}`); no SI conversion
  in M0 (that is `units.py`, M1-1).
- The schema does not check cross-references (lane ids, sensors, actuators).
  That is §5.5 compile-time validation and §5.8 static checks. The §6.1
  example lists `flt1`, `phc1`, `rhc1`, `sf1`, `rf1`, `ef1` in its lanes
  without defining them; it passes the schema and will fail later checks.
- Unknown keys are rejected (`extra="forbid"`) so typos fail loudly.
- `pressurization_bias.sign` accepts `supply_minus_return` or
  `return_minus_supply`.
- NumPy is in the §3 stack but nothing uses it yet; it is added (pinned)
  in M1 when first needed.
