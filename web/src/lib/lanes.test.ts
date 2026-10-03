import { describe, expect, it } from "vitest";
import exampleJson from "../../../engine/tests/fixtures/example_6_1.json";
import { allowedTypes, insertShared, insertSingle, layout, removeComponent } from "./lanes.ts";
import type { UnitConfig } from "./model.ts";

const example = exampleJson as unknown as UnitConfig;

const blank: UnitConfig = {
  schema_version: "0.2",
  unit: { name: "x", altitude: { value: 0, unit: "ft" }, pressure_override: null },
  airflows: {
    supply: { value: 10000, unit: "cfm", at: "supply_fan_discharge" },
    min_oa: { value: 2000, unit: "cfm", at: "oa_damper" },
    pressurization_bias: { value: 0, unit: "cfm", sign: "supply_minus_return" },
  },
  lanes: { supply: ["oa"], return: ["ra"] },
  components: {},
  sensors: [],
  sequence: { modes: [], loops: {} },
  conditions: {},
} as unknown as UnitConfig;

describe("lane editing", () => {
  it("inserts single-lane parts with sensible ids", () => {
    let [cfg, id] = insertSingle(blank, "fan", { lane: "supply", index: 1 });
    expect(id).toBe("sf1");
    [cfg, id] = insertSingle(cfg, "cooling_coil_chw", { lane: "supply", index: 1 });
    expect(id).toBe("cc1");
    expect(cfg.lanes.supply).toEqual(["oa", "cc1", "sf1"]);
    expect(blank.lanes.supply).toEqual(["oa"]); // input untouched
  });

  it("inserts shared parts in both lanes", () => {
    let [cfg] = insertShared(blank, "mixing_box", 1, 1);
    [cfg] = insertShared(cfg, "energy_wheel", 1, 2);
    expect(cfg.lanes.supply).toEqual(["oa", "erw1.supply", "mix1"]);
    expect(cfg.lanes.return).toEqual(["ra", "mix1", "erw1.exhaust"]);
  });

  it("names return fans by position relative to the mixing box", () => {
    let [cfg] = insertShared(blank, "mixing_box", 1, 1);
    let id: string;
    [cfg, id] = insertSingle(cfg, "fan", { lane: "return", index: 1 });
    expect(id).toBe("rf1");
    [cfg, id] = insertSingle(cfg, "fan", { lane: "return", index: 3 });
    expect(id).toBe("ef1");
  });

  it("removes a part from components and both lanes", () => {
    const cfg = removeComponent(example, "erw1");
    expect(cfg.lanes.supply).not.toContain("erw1.supply");
    expect(cfg.lanes.return).not.toContain("erw1.exhaust");
    expect("erw1" in cfg.components).toBe(false);
  });

  it("palette only offers what fits the selected slots", () => {
    expect(allowedTypes(blank, 1, null).has("cooling_coil_chw")).toBe(true);
    expect(allowedTypes(blank, 1, null).has("energy_wheel")).toBe(false);
    expect(allowedTypes(blank, null, 1)).toEqual(new Set(["fan", "filter"]));
    expect(allowedTypes(blank, 1, 1).has("mixing_box")).toBe(true);
    expect(allowedTypes(example, 1, 1).has("mixing_box")).toBe(false); // one max
  });
});

describe("schematic layout", () => {
  it("aligns parts that sit in both lanes in one column", () => {
    const placed = layout(example);
    const col = (token: string, lane: string) => placed.find((p) => p.token === token && p.lane === lane)!.column;
    expect(col("erw1.supply", "supply")).toBe(col("erw1.exhaust", "return"));
    expect(col("mix1", "supply")).toBe(col("mix1", "return"));
    expect(col("oa", "supply")).toBe(0);
    expect(placed.filter((p) => p.lane === "both").map((p) => p.token)).toEqual(["erw1", "mix1"]);
  });
});
