// Lane editing and schematic layout. Pure functions over the config: the
// engine validates topology; these only keep the lane lists consistent.
import { CROSS_LANE, SINGLE_TOKEN_BOTH_LANES, type UnitConfig } from "./model.ts";
import { TEMPLATES } from "./templates.ts";

export type Lane = "supply" | "return";
export type Slot = { lane: Lane; index: number }; // insert before lane[index]

const PREFIX: Record<string, string> = {
  mixing_box: "mix", filter: "flt", heating_coil_hw: "hc", electric_heater: "eh", cooling_coil_chw: "cc",
  steam_humidifier: "hum", adiabatic_humidifier: "evap", energy_wheel: "erw", plate_hx: "hx",
  runaround: "rac", heat_pipe: "hp", desiccant_wheel: "dw",
};

export const componentOf = (token: string) => token.split(".")[0];
export const typeOf = (cfg: UnitConfig, token: string) => cfg.components[componentOf(token)]?.type;
export const isShared = (cfg: UnitConfig, token: string) => {
  const t = typeOf(cfg, token);
  return t !== undefined && (CROSS_LANE.has(t) || t === SINGLE_TOKEN_BOTH_LANES);
};

function prefixFor(cfg: UnitConfig, type: string, lane: Lane, index: number): string {
  if (type !== "fan") return PREFIX[type] ?? type;
  if (lane === "supply") return "sf";
  const beforeBox = cfg.lanes.return.slice(0, index).some((t) => typeOf(cfg, t) === "mixing_box");
  return beforeBox ? "ef" : "rf";
}

export function nextId(cfg: UnitConfig, prefix: string): string {
  let n = 1;
  while (`${prefix}${n}` in cfg.components) n++;
  return `${prefix}${n}`;
}

const clone = (cfg: UnitConfig): UnitConfig => structuredClone(cfg);

/** Insert a single-lane component (or a fan) at a lane slot. Returns [cfg, id]. */
export function insertSingle(cfg: UnitConfig, type: string, slot: Slot): [UnitConfig, string] {
  const out = clone(cfg);
  const id = nextId(out, prefixFor(out, type, slot.lane, slot.index));
  out.components[id] = TEMPLATES[type]();
  out.lanes[slot.lane].splice(slot.index, 0, id);
  return [out, id];
}

/** Insert a component that sits in both lanes: mixing box (bare id) or exchanger (id.supply / id.exhaust). */
export function insertShared(cfg: UnitConfig, type: string, supply: number, ret: number): [UnitConfig, string] {
  const out = clone(cfg);
  const id = nextId(out, PREFIX[type] ?? type);
  out.components[id] = TEMPLATES[type]();
  const box = type === SINGLE_TOKEN_BOTH_LANES;
  out.lanes.supply.splice(supply, 0, box ? id : `${id}.supply`);
  out.lanes.return.splice(ret, 0, box ? id : `${id}.exhaust`);
  return [out, id];
}

export function removeComponent(cfg: UnitConfig, id: string): UnitConfig {
  const out = clone(cfg);
  delete out.components[id];
  out.lanes.supply = out.lanes.supply.filter((t) => componentOf(t) !== id);
  out.lanes.return = out.lanes.return.filter((t) => componentOf(t) !== id);
  return out;
}

/** Palette rule: what can go into the current slot selection. */
export function allowedTypes(cfg: UnitConfig, supply: number | null, ret: number | null): Set<string> {
  const ok = new Set<string>();
  const hasBox = Object.values(cfg.components).some((c) => c.type === "mixing_box");
  if (supply !== null && ret !== null) {
    for (const t of CROSS_LANE) ok.add(t);
    if (!hasBox) ok.add("mixing_box");
  } else if (supply !== null) {
    for (const t of Object.keys(TEMPLATES)) if (!CROSS_LANE.has(t) && t !== "mixing_box") ok.add(t);
  } else if (ret !== null) {
    ok.add("fan");
    ok.add("filter");
  }
  return ok;
}

export type Placed = { token: string; lane: Lane | "both"; index: number; column: number };

/**
 * Columns for the schematic: supply lane left→right above, return lane drawn
 * right→left below (as on a drawing), with parts that sit in both lanes in the
 * same column. Returns one entry per supply token, per return token, and one
 * "both" entry per shared component.
 */
export function layout(cfg: UnitConfig): Placed[] {
  const S = cfg.lanes.supply.map((t, i) => ({ t, i }));
  const R = cfg.lanes.return.map((t, i) => ({ t, i })).reverse();
  const out: Placed[] = [];
  let i = 0, j = 0, col = 0;
  const shared = (t: string) => t !== "oa" && t !== "ra" && isShared(cfg, t);
  while (i < S.length || j < R.length) {
    const s = S[i], r = R[j];
    if (s && r && shared(s.t) && shared(r.t) && componentOf(s.t) === componentOf(r.t)) {
      out.push({ token: s.t, lane: "supply", index: s.i, column: col });
      out.push({ token: r.t, lane: "return", index: r.i, column: col });
      out.push({ token: componentOf(s.t), lane: "both", index: -1, column: col });
      i++, j++;
    } else if (s && shared(s.t) && r && !shared(r.t)) {
      out.push({ token: r.t, lane: "return", index: r.i, column: col });
      j++;
    } else if (r && shared(r.t) && s && !shared(s.t)) {
      out.push({ token: s.t, lane: "supply", index: s.i, column: col });
      i++;
    } else {
      if (s) out.push({ token: s.t, lane: "supply", index: s.i, column: col }), i++;
      if (r) out.push({ token: r.t, lane: "return", index: r.i, column: col }), j++;
    }
    col++;
  }
  return out;
}
