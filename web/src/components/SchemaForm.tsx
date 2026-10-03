// A form generated from the engine's JSON Schema (src/types/unit-config.schema.json).
// Every component type in the engine gets an inspector without hand-written UI.
import { useEffect, useState } from "react";
import schema from "../types/unit-config.schema.json";

type Node = Record<string, any>; // a JSON Schema node
const ROOT = schema as Node;

export const UNIT_LABEL: Record<string, string> = {
  F: "°F", C: "°C", ft2: "ft²", m2: "m²", in_wc: "in. w.c.", m3s: "m³/s", "m3/s": "m³/s", "m3/h": "m³/h",
  fpm: "fpm", "m/s": "m/s", cfm: "cfm", "L/s": "L/s", ft: "ft", m: "m", Pa: "Pa", "%": "%",
  "Btu/lb": "Btu/lb", "kJ/kg": "kJ/kg", kW: "kW", W: "W", MBH: "MBH", "Btu/h": "Btu/h",
  "lb/h": "lb/h", "kg/h": "kg/h", "kg/s": "kg/s",
};

const KEY_LABEL: Record<string, string> = {
  eps_sens: "ε sensible", eps_lat: "ε latent", eatr: "EATR", eta_fan: "η fan", eta_motor: "η motor",
  dp_clean: "ΔP clean", dp_dirty: "ΔP dirty", total_static: "Total static ΔP (excl. filters)",
  oa: "Outdoor-air damper", ra: "Return damper", relief: "Relief damper", min_oa: "Minimum OA",
  pressurization_bias: "Pressurization bias", pressure_override: "Pressure override",
  motor_in_airstream: "Motor in airstream", max_face_velocity: "Max face velocity", regen_heat: "Regeneration heat",
};
const UPPER = new Set(["eat", "lat", "ewt", "lwt", "chws", "chwr", "oa", "ra", "rh", "ft"]);

export function label(key: string): string {
  if (KEY_LABEL[key]) return KEY_LABEL[key];
  const words = key.split("_").map((w) => (UPPER.has(w) ? w.toUpperCase() : w));
  const s = words.join(" ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function resolve(node: Node): Node {
  let n = node;
  while (n && n.$ref) n = ROOT.$defs[n.$ref.split("/").pop()];
  return n;
}

const constOf = (n: Node | undefined) => (n ? (n.const ?? (n.enum?.length === 1 ? n.enum[0] : undefined)) : undefined);

/** The schema definition for a component, matched on its type (and cooling-coil mode). */
export function componentDef(comp: { type: string; mode?: string }): Node | undefined {
  return Object.values(ROOT.$defs as Record<string, Node>).find((d) => {
    const p = d.properties ?? {};
    if (constOf(p.type) !== comp.type && !(p.type?.enum ?? []).includes(comp.type)) return false;
    return p.mode === undefined || constOf(p.mode) === comp.mode;
  });
}

export const defOf = (name: string): Node => ROOT.$defs[name];

function isQuantity(n: Node): boolean {
  const u = n.properties?.unit;
  return !!(n.properties?.value && u && (u.enum || u.const));
}

function nullable(n: Node): Node | null {
  const branches: Node[] = n.anyOf ?? [];
  if (branches.length === 2 && branches.some((b) => b.type === "null")) return branches.find((b) => b.type !== "null")!;
  return null;
}

function defaultFor(n: Node): unknown {
  const r = resolve(n);
  if (isQuantity(r)) return { value: 0, unit: (r.properties.unit.enum ?? [r.properties.unit.const])[0] };
  if (r.type === "boolean") return false;
  if (r.type === "number" || r.type === "integer") return r.minimum ?? 0;
  if (r.enum) return r.enum[0];
  if (r.type === "object" && r.properties) {
    return Object.fromEntries((r.required ?? []).map((k: string) => [k, defaultFor(r.properties[k])]));
  }
  return "";
}

/** Number input that keeps what the user is typing until it parses. */
export function NumberInput(props: { value: number; onChange: (v: number) => void; label?: string; step?: string }) {
  const [text, setText] = useState(String(props.value));
  useEffect(() => {
    if (Number(text) !== props.value) setText(String(props.value));
  }, [props.value]);
  return (
    <input
      className="num"
      inputMode="decimal"
      aria-label={props.label}
      value={text}
      onChange={(e) => {
        setText(e.target.value);
        const v = Number(e.target.value);
        if (e.target.value.trim() !== "" && Number.isFinite(v)) props.onChange(v);
      }}
    />
  );
}

export function QuantityField(props: { node: Node; value: any; onChange: (v: any) => void; name: string }) {
  const r = resolve(props.node);
  const units: string[] = r.properties.unit.enum ?? [r.properties.unit.const];
  const extra = Object.keys(r.properties).filter((k) => k !== "value" && k !== "unit");
  return (
    <div className="form-grid">
      <div className="qty">
        <NumberInput label={props.name} value={props.value.value} onChange={(v) => props.onChange({ ...props.value, value: v })} />
        <select aria-label={`${props.name} unit`} value={props.value.unit} onChange={(e) => props.onChange({ ...props.value, unit: e.target.value })}>
          {units.map((u) => (
            <option key={u} value={u}>{UNIT_LABEL[u] ?? u}</option>
          ))}
        </select>
      </div>
      {extra.map((k) => (
        <label key={k} className="field">
          {label(k)}
          <Field node={r.properties[k]} name={`${props.name} ${k}`} value={props.value[k]} onChange={(v) => props.onChange({ ...props.value, [k]: v })} />
        </label>
      ))}
    </div>
  );
}

export function Field(props: { node: Node; value: any; onChange: (v: any) => void; name: string }) {
  const opt = nullable(props.node);
  if (opt) {
    const on = props.value !== null && props.value !== undefined;
    return (
      <div className="form-grid">
        <label className="optional-toggle">
          <input type="checkbox" checked={on} onChange={(e) => props.onChange(e.target.checked ? defaultFor(opt) : null)} />
          {on ? "set" : "not set"}
        </label>
        {on && <Field node={opt} name={props.name} value={props.value} onChange={props.onChange} />}
      </div>
    );
  }
  const n = resolve(props.node);
  if (isQuantity(n)) return <QuantityField {...props} />;
  if (n.enum) {
    return (
      <select aria-label={props.name} value={props.value} onChange={(e) => props.onChange(e.target.value)}>
        {n.enum.map((v: string) => (
          <option key={v} value={v}>{v}</option>
        ))}
      </select>
    );
  }
  if (n.type === "boolean") {
    return <input type="checkbox" aria-label={props.name} checked={!!props.value} onChange={(e) => props.onChange(e.target.checked)} />;
  }
  if (n.type === "number" || n.type === "integer") {
    return <NumberInput label={props.name} value={props.value ?? 0} onChange={props.onChange} />;
  }
  if (n.type === "object" && n.properties) return <ObjectFields node={n} value={props.value ?? {}} onChange={props.onChange} name={props.name} />;
  return <input aria-label={props.name} value={props.value ?? ""} onChange={(e) => props.onChange(e.target.value)} />;
}

export function ObjectFields(props: { node: Node; value: any; onChange: (v: any) => void; name?: string; skip?: string[] }) {
  const n = resolve(props.node);
  const keys = Object.keys(n.properties).filter((k) => !(props.skip ?? []).includes(k) && constOf(resolve(n.properties[k])) === undefined);
  return (
    <div className="form-grid">
      {keys.map((k) => {
        const child = resolve(n.properties[k]);
        const nested = child.type === "object" && child.properties && !isQuantity(child);
        const field = (
          <Field
            node={n.properties[k]}
            name={label(k)}
            value={props.value[k]}
            onChange={(v) => props.onChange({ ...props.value, [k]: v })}
          />
        );
        return nested ? (
          <fieldset key={k}>
            <legend>{label(k)}</legend>
            {field}
          </fieldset>
        ) : (
          <label key={k} className="field">
            {label(k)}
            {field}
          </label>
        );
      })}
    </div>
  );
}
