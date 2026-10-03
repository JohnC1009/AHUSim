// Workspace state for the open unit (zustand). Results and display values come
// from the API; nothing here computes a physical quantity.
import { create } from "zustand";
import type { ConditionOut, FailureOut } from "./api.ts";
import type { UnitConfig, UnitSystem } from "./lib/model.ts";

const savedUnits = (): UnitSystem => {
  try {
    return localStorage.getItem("units") === "si" ? "si" : "ip";
  } catch {
    return "ip";
  }
};

type Workspace = {
  unitId: string | null;
  config: UnitConfig | null;
  version: number;
  dirty: boolean;
  units: UnitSystem;
  selected: string | null; // component id, or null for unit settings
  slot: { supply: number | null; ret: number | null };
  hovered: string | null; // state key, e.g. "after:cc1"
  conditionId: string | null;
  results: Record<string, ConditionOut>;
  staticFailures: FailureOut[];
  pressure: number | null;
  error: string | null;
  load: (unitId: string, config: UnitConfig, version: number) => void;
  edit: (config: UnitConfig) => void;
  saved: (version: number) => void;
  setUnits: (u: UnitSystem) => void;
  select: (id: string | null) => void;
  pickSlot: (lane: "supply" | "ret", index: number | null) => void;
  hover: (key: string | null) => void;
  setCondition: (id: string | null) => void;
  setResults: (r: ConditionOut[], staticFailures: FailureOut[], p: number) => void;
  setResult: (r: ConditionOut, staticFailures: FailureOut[], p: number) => void;
  setError: (e: string | null) => void;
};

export const useWorkspace = create<Workspace>((set) => ({
  unitId: null,
  config: null,
  version: 0,
  dirty: false,
  units: savedUnits(),
  selected: null,
  slot: { supply: null, ret: null },
  hovered: null,
  conditionId: null,
  results: {},
  staticFailures: [],
  pressure: null,
  error: null,
  load: (unitId, config, version) =>
    set({ unitId, config, version, dirty: false, results: {}, selected: null, slot: { supply: null, ret: null }, error: null,
          conditionId: config.conditions.operating?.[0]?.id ?? null }),
  edit: (config) => set({ config, dirty: true }),
  saved: (version) => set({ version, dirty: false }),
  setUnits: (units) => {
    try {
      localStorage.setItem("units", units);
    } catch {
      /* private window: keep in memory only */
    }
    set({ units, results: {} });
  },
  select: (selected) => set({ selected }),
  pickSlot: (lane, index) => set((s) => ({ slot: { ...s.slot, [lane]: s.slot[lane] === index ? null : index } })),
  hover: (hovered) => set({ hovered }),
  setCondition: (conditionId) => set({ conditionId }),
  setResults: (results, staticFailures, pressure) =>
    set({ results: Object.fromEntries(results.map((r) => [r.condition_id, r])), staticFailures, pressure, error: null }),
  setResult: (r, staticFailures, pressure) =>
    set((s) => ({ results: { ...s.results, [r.condition_id]: r }, staticFailures, pressure, error: null })),
  setError: (error) => set({ error }),
}));
