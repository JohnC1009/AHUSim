// Structured mode conditions (spec §5.6): groups of all / any / not and
// comparisons. Data only — the engine evaluates them; nothing is eval'd.
import { CONDITION_VARS, VAR_LABEL, varUnits, type Condition } from "../lib/model.ts";
import { NumberInput, UNIT_LABEL } from "./SchemaForm.tsx";

type Cmp = { var: string; op: string; value: unknown };
const OPS = ["<", "<=", ">", ">=", "=="];
const isGroup = (c: Condition): c is Condition & ({ all: Condition[] } | { any: Condition[] }) => "all" in c || "any" in c;
const newComparison = (): Cmp => ({ var: "oa_db", op: "<", value: { value: 55, unit: "F" } });

function Comparison({ c, onChange, onRemove }: { c: Cmp; onChange: (c: Cmp) => void; onRemove?: () => void }) {
  const units = varUnits(c.var);
  const q = c.value as { value: number; unit: string };
  return (
    <div className="cond">
      <select
        aria-label="Variable"
        value={c.var}
        onChange={(e) => {
          const v = e.target.value;
          const u = varUnits(v);
          onChange({ var: v, op: v === "schedule" ? "==" : c.op, value: v === "schedule" ? "occupied" : { value: typeof q === "object" ? q.value : 0, unit: u[0] } });
        }}
      >
        {CONDITION_VARS.map((v) => (
          <option key={v} value={v}>{VAR_LABEL[v]}</option>
        ))}
      </select>
      <select aria-label="Operator" value={c.op} disabled={c.var === "schedule"} onChange={(e) => onChange({ ...c, op: e.target.value })}>
        {OPS.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
      {c.var === "schedule" ? (
        <input aria-label="Schedule name" value={c.value as string} onChange={(e) => onChange({ ...c, value: e.target.value })} />
      ) : (
        <>
          <NumberInput label="Threshold" value={q.value} onChange={(v) => onChange({ ...c, value: { ...q, value: v } })} />
          <select aria-label="Threshold unit" value={q.unit} onChange={(e) => onChange({ ...c, value: { ...q, unit: e.target.value } })}>
            {units.map((u) => (
              <option key={u} value={u}>{UNIT_LABEL[u] ?? u}</option>
            ))}
          </select>
        </>
      )}
      {onRemove && <button className="btn" onClick={onRemove}>Remove</button>}
    </div>
  );
}

export function ConditionEditor({ value, onChange, onRemove }: { value: Condition; onChange: (c: Condition) => void; onRemove?: () => void }) {
  if ("not" in value) {
    return (
      <div className="cond-group">
        <div className="row"><span className="chip">NOT</span>{onRemove && <button className="btn" onClick={onRemove}>Remove group</button>}</div>
        <ConditionEditor value={value.not as Condition} onChange={(c) => onChange({ not: c } as Condition)} />
      </div>
    );
  }
  if (isGroup(value)) {
    const key = "all" in value ? "all" : "any";
    const items = (value as unknown as Record<string, Condition[]>)[key];
    const set = (list: Condition[]) => onChange({ [key]: list } as unknown as Condition);
    return (
      <div className="cond-group">
        <div className="row">
          <span className="chip">{key === "all" ? "ALL of" : "ANY of"}</span>
          <select aria-label="Group type" value={key} onChange={(e) => onChange({ [e.target.value]: items } as unknown as Condition)}>
            <option value="all">all</option>
            <option value="any">any</option>
          </select>
          {onRemove && <button className="btn" onClick={onRemove}>Remove group</button>}
        </div>
        {items.map((c, i) => (
          <ConditionEditor
            key={i}
            value={c}
            onChange={(n) => set(items.map((x, j) => (j === i ? n : x)))}
            onRemove={items.length > 1 ? () => set(items.filter((_, j) => j !== i)) : undefined}
          />
        ))}
        <div className="row">
          <button className="btn" onClick={() => set([...items, newComparison() as Condition])}>+ Condition</button>
          <button className="btn" onClick={() => set([...items, { all: [newComparison()] } as unknown as Condition])}>+ Group</button>
          <button className="btn" onClick={() => set([...items, { not: newComparison() } as unknown as Condition])}>+ NOT</button>
        </div>
      </div>
    );
  }
  return <Comparison c={value as Cmp} onChange={(c) => onChange(c as Condition)} onRemove={onRemove} />;
}

/** Wrap a single comparison in an "all" group so more can be added. */
export const asGroup = (c: Condition): Condition => (isGroup(c) || "not" in c ? c : ({ all: [c] } as unknown as Condition));
