import { NumberInput, UNIT_LABEL } from "../components/SchemaForm.tsx";
import type { OperatingCondition } from "../lib/model.ts";
import { useWorkspace } from "../store.ts";

type Q = { value: number; unit: string };

function Qty({ q, units, onChange, label }: { q: Q; units: string[]; onChange: (q: Q) => void; label: string }) {
  return (
    <span className="qty">
      <NumberInput label={label} value={q.value} onChange={(v) => onChange({ ...q, value: v })} />
      <select aria-label={`${label} unit`} value={q.unit} onChange={(e) => onChange({ ...q, unit: e.target.value })}>
        {units.map((u) => <option key={u} value={u}>{UNIT_LABEL[u] ?? u}</option>)}
      </select>
    </span>
  );
}

// Illustrative values only — not ASHRAE design data (licensing is open question §14-3).
const NEW_CONDITION = (n: number): OperatingCondition => ({
  id: `condition${n}`,
  oa_db: { value: 91, unit: "F" },
  oa_wb: { value: 74, unit: "F" },
  ra_db: { value: 75, unit: "F" },
  ra_rh: { value: 50, unit: "%" },
  schedule: "occupied",
});

export function ConditionsPage() {
  const { config, edit } = useWorkspace();
  if (!config) return null;
  const list = config.conditions.operating ?? [];
  const set = (operating: OperatingCondition[]) => edit({ ...config, conditions: { ...config.conditions, operating } });
  const upd = (i: number, c: OperatingCondition) => set(list.map((x, j) => (j === i ? c : x)));
  return (
    <main className="main">
      <div className="stack">
        <div className="row">
          <h2>Operating conditions</h2>
          <div className="spacer" />
          <button className="btn" onClick={() => set([...list, NEW_CONDITION(list.length + 1)])}>+ Condition</button>
        </div>
        <p className="hint">New conditions start at illustrative summer values (91 °F db / 74 °F wb). Design-day data arrives in M4.</p>
        {list.map((c, i) => {
          const useWb = c.oa_wb !== null && c.oa_wb !== undefined;
          return (
            <div key={i} className="card stack">
              <div className="row">
                <label className="field">Id<input aria-label="Condition id" value={c.id} onChange={(e) => upd(i, { ...c, id: e.target.value })} /></label>
                <label className="field">Schedule<input aria-label="Schedule" value={c.schedule ?? ""} onChange={(e) => upd(i, { ...c, schedule: e.target.value || null })} /></label>
                <div className="spacer" />
                <button className="btn danger" onClick={() => set(list.filter((_, j) => j !== i))}>Delete</button>
              </div>
              <div className="grid-2">
                <label className="field">OA dry bulb<Qty label="OA dry bulb" q={c.oa_db} units={["F", "C"]} onChange={(q) => upd(i, { ...c, oa_db: q as OperatingCondition["oa_db"] })} /></label>
                <label className="field">
                  <span className="row">
                    OA humidity as
                    <select aria-label="OA humidity input" value={useWb ? "wb" : "rh"} onChange={(e) =>
                      upd(i, e.target.value === "wb"
                        ? { ...c, oa_wb: { value: 65, unit: "F" }, oa_rh: null }
                        : { ...c, oa_wb: null, oa_rh: { value: 50, unit: "%" } })}>
                      <option value="wb">wet bulb</option>
                      <option value="rh">RH</option>
                    </select>
                  </span>
                  {useWb
                    ? <Qty label="OA wet bulb" q={c.oa_wb!} units={["F", "C"]} onChange={(q) => upd(i, { ...c, oa_wb: q as OperatingCondition["oa_db"] })} />
                    : <Qty label="OA RH" q={c.oa_rh!} units={["%"]} onChange={(q) => upd(i, { ...c, oa_rh: q as NonNullable<OperatingCondition["oa_rh"]> })} />}
                </label>
                <label className="field">RA dry bulb<Qty label="RA dry bulb" q={c.ra_db} units={["F", "C"]} onChange={(q) => upd(i, { ...c, ra_db: q as OperatingCondition["ra_db"] })} /></label>
                <label className="field">RA RH<Qty label="RA RH" q={c.ra_rh} units={["%"]} onChange={(q) => upd(i, { ...c, ra_rh: q as OperatingCondition["ra_rh"] })} /></label>
              </div>
            </div>
          );
        })}
      </div>
    </main>
  );
}
