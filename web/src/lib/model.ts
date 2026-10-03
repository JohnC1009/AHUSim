// Type aliases over the generated config types (src/types/config.ts).
import type { OperatingCondition, UnitConfig } from "../types/config.ts";

export type { OperatingCondition, UnitConfig };
export type Component = UnitConfig["components"][string];
export type Mode = UnitConfig["sequence"]["modes"][number];
export type Loop = UnitConfig["sequence"]["loops"][string];
export type Condition = Mode["enter"];
export type Quantity = { value: number; unit: string };
export type UnitSystem = "ip" | "si";

/** Components that span both lanes (spec §5.2): written "<id>.supply" / "<id>.exhaust". */
export const CROSS_LANE = new Set(["energy_wheel", "plate_hx", "runaround", "heat_pipe", "desiccant_wheel"]);
export const SINGLE_TOKEN_BOTH_LANES = "mixing_box";

export const COMPONENT_LABELS: Record<string, string> = {
  mixing_box: "Mixing box",
  filter: "Filter",
  heating_coil_hw: "Heating coil (HW)",
  electric_heater: "Electric heater",
  cooling_coil_chw: "Cooling coil (CHW)",
  steam_humidifier: "Steam humidifier",
  adiabatic_humidifier: "Adiabatic humidifier",
  energy_wheel: "Energy wheel",
  plate_hx: "Plate heat exchanger",
  runaround: "Runaround loop",
  heat_pipe: "Heat pipe",
  desiccant_wheel: "Desiccant wheel",
  fan: "Fan",
  space: "Space",
};

/** Schematic symbol (tokens.symbols key) for each component type. */
export const SYMBOL: Record<string, string> = {
  mixing_box: "damper",
  filter: "filter",
  heating_coil_hw: "coil",
  electric_heater: "coil",
  cooling_coil_chw: "coil",
  steam_humidifier: "humidifier",
  adiabatic_humidifier: "humidifier",
  energy_wheel: "wheel",
  desiccant_wheel: "wheel",
  plate_hx: "coil",
  runaround: "coil",
  heat_pipe: "coil",
  fan: "fan",
};

/** Actuators by component type (names the engine's controls accept). */
export const ACTUATORS: Record<string, string[]> = {
  mixing_box: ["oa_fraction"],
  heating_coil_hw: ["valve"],
  cooling_coil_chw: ["valve"],
  electric_heater: ["output"],
  steam_humidifier: ["output"],
  adiabatic_humidifier: ["output"],
  desiccant_wheel: ["output"],
  energy_wheel: ["bypass", "speed"],
  plate_hx: ["bypass"],
  runaround: ["bypass"],
  heat_pipe: ["bypass"],
};

export function actuatorRefs(cfg: UnitConfig): string[] {
  return Object.entries(cfg.components).flatMap(([id, c]) =>
    c.type === "cooling_coil_chw" && (c as { mode?: string }).mode === "measured" ? [] : (ACTUATORS[c.type] ?? []).map((a) => `${id}.${a}`),
  );
}

export const CONDITION_VARS = ["oa_db", "oa_h", "oa_dp", "ra_db", "ra_h", "space_t", "schedule"] as const;
export const VAR_LABEL: Record<string, string> = {
  oa_db: "OA dry bulb", oa_h: "OA enthalpy", oa_dp: "OA dew point", ra_db: "RA dry bulb", ra_h: "RA enthalpy",
  space_t: "Space temperature", schedule: "Schedule",
};
export const varUnits = (v: string) => (v === "schedule" ? [] : v.endsWith("_h") ? ["Btu/lb", "kJ/kg"] : ["F", "C"]);
