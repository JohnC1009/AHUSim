// Starting parameters for a component dropped into a lane, in I-P.
// Engineering defaults only (the §6.1 / decision-0002 values); the engine
// computes everything. Edit them in the inspector.
import type { Component } from "./model.ts";

const F = (value: number) => ({ value, unit: "F" as const });
const cfm = (value: number) => ({ value, unit: "cfm" as const });
const inwc = (value: number) => ({ value, unit: "in_wc" as const });
const ft2 = (value: number) => ({ value, unit: "ft2" as const });
const fpm = (value: number) => ({ value, unit: "fpm" as const });
const damper = (area: number) => ({ free_area: ft2(area), max_velocity: fpm(1500) });

export const TEMPLATES: Record<string, () => Component> = {
  mixing_box: () => ({ type: "mixing_box", dampers: { oa: damper(8), ra: damper(4.5), relief: damper(6) } }),
  filter: () => ({ type: "filter", dp_clean: inwc(0.35), dp_dirty: inwc(1.0) }),
  heating_coil_hw: () => ({
    type: "heating_coil_hw",
    face_area: ft2(22),
    max_face_velocity: fpm(500),
    rating: { eat: F(40), lat: F(90), airflow: cfm(10000), ewt: F(180), lwt: F(160) },
  }),
  electric_heater: () => ({ type: "electric_heater", power: { value: 30, unit: "kW" as const } }),
  cooling_coil_chw: () => ({
    type: "cooling_coil_chw",
    mode: "design",
    face_area: ft2(22),
    max_face_velocity: fpm(500),
    rating: {
      eat_db: F(80.5), eat_wb: F(67), lat_db: F(55), lat_wb: F(54),
      airflow: cfm(10000), chws: F(44), chwr: F(56),
    },
  }),
  steam_humidifier: () => ({
    type: "steam_humidifier",
    max_rate: { value: 100, unit: "lb/h" as const },
    absorption_distance: { value: 3, unit: "ft" as const },
  }),
  adiabatic_humidifier: () => ({ type: "adiabatic_humidifier", effectiveness: 0.85, max_rate: { value: 200, unit: "lb/h" as const } }),
  energy_wheel: () => ({ type: "energy_wheel", eps_sens: 0.75, eps_lat: 0.65, purge: true, eatr: 0.02 }),
  plate_hx: () => ({ type: "plate_hx", eps_sens: 0.6 }),
  runaround: () => ({ type: "runaround", eps_sens: 0.5 }),
  heat_pipe: () => ({ type: "heat_pipe", eps_sens: 0.5 }),
  desiccant_wheel: () => ({ type: "desiccant_wheel", eps_lat: 0.5, regen_heat: { value: 50, unit: "kW" as const } }),
  fan: () => ({
    type: "fan",
    design_airflow: cfm(10000),
    total_static: inwc(4.0),
    eta_fan: 0.65,
    eta_motor: 0.92,
    motor_in_airstream: true,
  }),
};
