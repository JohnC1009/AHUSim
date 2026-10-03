import { useState } from "react";
import { asGroup, ConditionEditor } from "../components/ConditionEditor.tsx";
import { NumberInput, UNIT_LABEL } from "../components/SchemaForm.tsx";
import { actuatorRefs, type Loop, type Mode } from "../lib/model.ts";
import { useWorkspace } from "../store.ts";

type Sel = { kind: "mode"; index: number } | { kind: "loop"; id: string } | null;

function ModeEditor({ index }: { index: number }) {
  const { config, edit } = useWorkspace();
  const mode = config!.sequence.modes[index];
  const refs = actuatorRefs(config!);
  const loopIds = Object.keys(config!.sequence.loops);
  const set = (m: Mode) => edit({ ...config!, sequence: { ...config!.sequence, modes: config!.sequence.modes.map((x, i) => (i === index ? m : x)) } });
  const fixed = mode.fixed ?? {};
  const unfixed = refs.filter((r) => !(r in fixed));
  return (
    <div className="card stack">
      <div className="row">
        <label className="field">Mode id<input aria-label="Mode id" value={mode.id} onChange={(e) => set({ ...mode, id: e.target.value })} /></label>
        <label className="field">Priority<NumberInput label="Priority" value={mode.priority} onChange={(v) => set({ ...mode, priority: Math.round(v) })} /></label>
        <div className="spacer" />
        <button className="btn danger" onClick={() => edit({ ...config!, sequence: { ...config!.sequence, modes: config!.sequence.modes.filter((_, i) => i !== index) } })}>Delete mode</button>
      </div>
      <p className="hint">Modes are evaluated in ascending priority; the first whose condition is true is active.</p>
      <h3>Enter when</h3>
      <ConditionEditor value={asGroup(mode.enter)} onChange={(c) => set({ ...mode, enter: c })} />
      <h3>Fixed positions (applied before loops)</h3>
      <table>
        <thead><tr><th>Actuator</th><th className="n">Position (%)</th><th /></tr></thead>
        <tbody>
          {Object.entries(fixed).map(([ref, v]) => (
            <tr key={ref}>
              <td className="mono">{ref}</td>
              <td className="n"><NumberInput label={`${ref} position`} value={Math.round(v * 1000) / 10} onChange={(p) => set({ ...mode, fixed: { ...fixed, [ref]: Math.min(Math.max(p / 100, 0), 1) } })} /></td>
              <td><button className="btn" onClick={() => { const f = { ...fixed }; delete f[ref]; set({ ...mode, fixed: f }); }}>Remove</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {unfixed.length > 0 && (
        <select aria-label="Fix an actuator" value="" onChange={(e) => e.target.value && set({ ...mode, fixed: { ...fixed, [e.target.value]: 0 } })}>
          <option value="">+ Fix an actuator…</option>
          {unfixed.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
      )}
      <h3>Loops in this mode (solved in this order)</h3>
      {loopIds.length === 0 && <p className="hint">Add a loop first.</p>}
      {loopIds.map((id) => (
        <label key={id} className="optional-toggle">
          <input
            type="checkbox"
            aria-label={`Run loop ${id}`}
            checked={(mode.loops ?? []).includes(id)}
            onChange={(e) => set({ ...mode, loops: e.target.checked ? [...(mode.loops ?? []), id] : (mode.loops ?? []).filter((l) => l !== id) })}
          />
          {id}
        </label>
      ))}
    </div>
  );
}

function LoopEditor({ id, onRename }: { id: string; onRename: (id: string) => void }) {
  const { config, edit } = useWorkspace();
  const loop = config!.sequence.loops[id];
  const refs = actuatorRefs(config!);
  const set = (l: Loop) => edit({ ...config!, sequence: { ...config!.sequence, loops: { ...config!.sequence.loops, [id]: l } } });
  const rename = (to: string) => {
    if (!to || to in config!.sequence.loops) return;
    const loops = Object.fromEntries(Object.entries(config!.sequence.loops).map(([k, v]) => [k === id ? to : k, v]));
    const modes = config!.sequence.modes.map((m) => ({ ...m, loops: (m.loops ?? []).map((l) => (l === id ? to : l)) }));
    edit({ ...config!, sequence: { modes, loops } });
    onRename(to);
  };
  const [name, setName] = useState(id);
  return (
    <div className="card stack">
      <div className="row">
        <label className="field">Loop id<input aria-label="Loop id" value={name} onChange={(e) => setName(e.target.value)} onBlur={() => rename(name)} /></label>
        <div className="spacer" />
        <button className="btn danger" onClick={() => {
          const loops = { ...config!.sequence.loops }; delete loops[id];
          edit({ ...config!, sequence: { modes: config!.sequence.modes.map((m) => ({ ...m, loops: (m.loops ?? []).filter((l) => l !== id) })), loops } });
          onRename("");
        }}>Delete loop</button>
      </div>
      <div className="grid-2">
        <label className="field">Sensor
          <select aria-label="Loop sensor" value={loop.sensor} onChange={(e) => set({ ...loop, sensor: e.target.value })}>
            {[...new Set([loop.sensor, ...config!.sensors.map((s) => s.id)])].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <label className="field">Setpoint
          <span className="qty">
            <NumberInput label="Setpoint" value={loop.setpoint.value} onChange={(v) => set({ ...loop, setpoint: { ...loop.setpoint, value: v } })} />
            <select aria-label="Setpoint unit" value={loop.setpoint.unit} onChange={(e) => set({ ...loop, setpoint: { ...loop.setpoint, unit: e.target.value as "F" | "C" } })}>
              {["F", "C"].map((u) => <option key={u} value={u}>{UNIT_LABEL[u]}</option>)}
            </select>
          </span>
        </label>
        <label className="field">Role
          <select aria-label="Loop role" value={loop.role ?? ""} onChange={(e) => set({ ...loop, role: (e.target.value || null) as Loop["role"] })}>
            <option value="">—</option>
            <option value="preheat">preheat</option>
            <option value="freeze_protection">freeze protection</option>
          </select>
        </label>
      </div>
      <h3>Stages (each parks at its end before the next moves)</h3>
      {loop.stages.map((s, i) => (
        <div key={i} className="stage">
          <span className="ord num">{i + 1}</span>
          <select aria-label={`Stage ${i + 1} actuator`} value={s.actuator} onChange={(e) => set({ ...loop, stages: loop.stages.map((x, j) => (j === i ? { ...x, actuator: e.target.value } : x)) as Loop["stages"] })}>
            {[...new Set([s.actuator, ...refs])].map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <select aria-label={`Stage ${i + 1} action`} value={s.action} onChange={(e) => set({ ...loop, stages: loop.stages.map((x, j) => (j === i ? { ...x, action: e.target.value as "direct" | "reverse" } : x)) as Loop["stages"] })}>
            <option value="direct">direct</option>
            <option value="reverse">reverse</option>
          </select>
          <button className="btn" disabled={loop.stages.length === 1} onClick={() => set({ ...loop, stages: loop.stages.filter((_, j) => j !== i) as Loop["stages"] })}>Remove</button>
        </div>
      ))}
      <div className="row">
        <button className="btn" disabled={refs.length === 0} onClick={() => set({ ...loop, stages: [...loop.stages, { actuator: refs[0], action: "direct" }] })}>+ Stage</button>
      </div>
    </div>
  );
}

export function SequencePage() {
  const { config, edit } = useWorkspace();
  const [sel, setSel] = useState<Sel>(null);
  if (!config) return null;
  const seq = config.sequence;
  const refs = actuatorRefs(config);
  const addMode = () => {
    const n = seq.modes.length + 1;
    const mode = { id: `mode${n}`, priority: n, enter: { var: "schedule", op: "==", value: "occupied" }, fixed: {}, loops: [] } as unknown as Mode;
    edit({ ...config, sequence: { ...seq, modes: [...seq.modes, mode] } });
    setSel({ kind: "mode", index: seq.modes.length });
  };
  const addLoop = () => {
    let n = 1;
    while (`loop${n}` in seq.loops) n++;
    const id = `loop${n}`;
    const loop: Loop = { sensor: config.sensors[0]?.id ?? "", setpoint: { value: 55, unit: "F" }, stages: [{ actuator: refs[0] ?? "", action: "direct" }] };
    edit({ ...config, sequence: { ...seq, loops: { ...seq.loops, [id]: loop } } });
    setSel({ kind: "loop", id });
  };
  return (
    <div className="page three">
      <aside className="panel stack">
        <div className="row"><h3>Modes</h3><div className="spacer" /><button className="btn" onClick={addMode}>+ Mode</button></div>
        <ul className="list">
          {seq.modes.map((m, i) => (
            <li key={i} className="clickable" aria-selected={sel?.kind === "mode" && sel.index === i} onClick={() => setSel({ kind: "mode", index: i })}>
              <span className="badge num">{m.priority}</span>{m.id}
            </li>
          ))}
        </ul>
        <div className="row"><h3>Loops</h3><div className="spacer" /><button className="btn" onClick={addLoop} disabled={refs.length === 0}>+ Loop</button></div>
        <ul className="list">
          {Object.keys(seq.loops).map((id) => (
            <li key={id} className="clickable" aria-selected={sel?.kind === "loop" && sel.id === id} onClick={() => setSel({ kind: "loop", id })}>{id}</li>
          ))}
        </ul>
      </aside>
      <main className="main">
        {sel?.kind === "mode" && seq.modes[sel.index] && <ModeEditor index={sel.index} />}
        {sel?.kind === "loop" && seq.loops[sel.id] && <LoopEditor key={sel.id} id={sel.id} onRename={(id) => setSel(id ? { kind: "loop", id } : null)} />}
        {!sel && <p className="empty">Pick or add a mode or loop.</p>}
      </main>
      <aside className="panel right stack">
        <h3>Static checks</h3>
        <StaticChecks />
      </aside>
    </div>
  );
}

function StaticChecks() {
  const { staticFailures } = useWorkspace();
  if (staticFailures.length === 0) return <p className="hint">No issues found.</p>;
  return (
    <div className="stack tight">
      {staticFailures.map((f, i) => (
        <div key={i} className="issue">
          <span className={`status ${f.severity === "warning" ? "warning" : "fail"}`}>
            <svg className="icon"><use href={`#status-${f.severity === "warning" ? "warning" : "fail"}`} /></svg>
          </span>
          <span>{f.message}</span>
        </div>
      ))}
    </div>
  );
}
