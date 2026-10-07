import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { failuresInView } from "./FailureStrip.tsx";
import { processKeys } from "./PsychChart.tsx";
import { componentDef, defOf, label, ObjectFields } from "./SchemaForm.tsx";

describe("schema-driven form", () => {
  it("finds a component's definition by type and coil mode", () => {
    expect(componentDef({ type: "fan" })?.properties.eta_fan).toBeTruthy();
    expect(componentDef({ type: "cooling_coil_chw", mode: "design" })?.properties.rating).toBeTruthy();
    expect(componentDef({ type: "cooling_coil_chw", mode: "measured" })?.properties.leaving).toBeTruthy();
  });

  it("edits a quantity's value and unit", () => {
    let value = { type: "filter", dp_clean: { value: 0.35, unit: "in_wc" }, dp_dirty: { value: 1, unit: "in_wc" } };
    const { rerender } = render(<ObjectFields node={componentDef({ type: "filter" })!} value={value} onChange={(v) => (value = v)} />);
    fireEvent.change(screen.getByLabelText("ΔP clean"), { target: { value: "0.5" } });
    expect(value.dp_clean).toEqual({ value: 0.5, unit: "in_wc" });
    rerender(<ObjectFields node={componentDef({ type: "filter" })!} value={value} onChange={(v) => (value = v)} />);
    fireEvent.change(screen.getByLabelText("ΔP dirty unit"), { target: { value: "Pa" } });
    expect(value.dp_dirty).toEqual({ value: 1, unit: "Pa" });
  });

  it("toggles an optional field", () => {
    let unit: Record<string, unknown> = { name: "AHU-1", altitude: { value: 0, unit: "ft" }, pressure_override: null };
    render(<ObjectFields node={defOf("UnitInfo")} value={unit} onChange={(v) => (unit = v)} />);
    fireEvent.click(screen.getByRole("checkbox"));
    expect(unit.pressure_override).toEqual({ value: 0, unit: "Pa" });
  });

  it("labels engineering keys readably", () => {
    expect(label("eat_db")).toBe("EAT db");
    expect(label("eps_lat")).toBe("ε latent");
    expect(label("free_area")).toBe("Free area");
  });
});

describe("result views", () => {
  it("shows each failure once, condition failures first", () => {
    const f = (message: string) => ({ kind: "limit_exceeded", severity: "error" as const, message, component: null, mode: null, condition_id: null });
    expect(failuresInView([f("a"), f("b")], [f("b"), f("c")]).map((x) => x.message)).toEqual(["b", "c", "a"]);
  });

  it("orders the process path along the supply lane", () => {
    const states = ["ra", "oa_intake", "after:mix1", "after:cc1", "after:sf1"].map((key) => ({ key, db: 0, wb: 0, dp: 0, rh: 0, w: 0, h: 0, v: 0, flow: 0 }));
    const r = { states } as never;
    expect(processKeys(r, ["oa", "mix1", "cc1", "sf1"])).toEqual(["oa_intake", "after:mix1", "after:cc1", "after:sf1"]);
  });
});

describe("energy wheel form", () => {
  it("adds and removes an airflow rating point", () => {
    let value: Record<string, any> = { type: "energy_wheel", eps_sens: 0.75, eps_lat: 0.65, purge: true, eatr: 0.02 };
    const node = componentDef({ type: "energy_wheel" })!;
    const { rerender } = render(<ObjectFields node={node} value={value} onChange={(v) => (value = v)} />);
    fireEvent.click(screen.getByRole("button", { name: "+ Add More airflow ratings" }));
    expect(value.airflow_ratings).toEqual([{ airflow: { value: 0, unit: "cfm" }, eps_sens: 0, eps_lat: 0 }]);
    rerender(<ObjectFields node={node} value={value} onChange={(v) => (value = v)} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove More airflow ratings 1" }));
    expect(value.airflow_ratings).toEqual([]);
    expect(screen.getByText("OACF (OA in / supply out)")).toBeTruthy();
  });
});
