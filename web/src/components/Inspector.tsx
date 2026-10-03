import { componentDef, defOf, label, ObjectFields } from "./SchemaForm.tsx";
import { StatusIcon } from "./TopBar.tsx";
import { removeComponent } from "../lib/lanes.ts";
import { COMPONENT_LABELS, type UnitConfig } from "../lib/model.ts";
import { useWorkspace } from "../store.ts";

function lanePoints(cfg: UnitConfig): string[] {
  const box = Object.entries(cfg.components).find(([, c]) => c.type === "mixing_box")?.[0];
  return [
    ...cfg.lanes.supply.slice(1).map((t) => `after:${t}`),
    ...cfg.lanes.return.slice(1).map((t) => (t === box ? `after:${t}.relief` : `after:${t}`)),
  ];
}

function Sensors() {
  const { config, edit } = useWorkspace();
  if (!config) return null;
  const points = lanePoints(config);
  const set = (sensors: UnitConfig["sensors"]) => edit({ ...config, sensors });
  return (
    <div className="stack tight">
      <h3>Sensors</h3>
      {config.sensors.map((s, i) => (
        <div key={i} className="grid-2 card">
          <input aria-label="Sensor id" value={s.id} onChange={(e) => set(config.sensors.map((x, j) => (j === i ? { ...x, id: e.target.value } : x)))} />
          <select aria-label={`${s.id} type`} value={s.type} onChange={(e) => set(config.sensors.map((x, j) => (j === i ? { ...x, type: e.target.value as typeof s.type } : x)))}>
            <option value="temperature">temperature</option>
            <option value="temperature_averaging">temperature (averaging)</option>
          </select>
          <select aria-label={`${s.id} location`} value={s.at} onChange={(e) => set(config.sensors.map((x, j) => (j === i ? { ...x, at: e.target.value } : x)))}>
            {[...new Set([s.at, ...points])].map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
          <button className="btn" onClick={() => set(config.sensors.filter((_, j) => j !== i))}>Remove</button>
        </div>
      ))}
      <button
        className="btn"
        disabled={points.length === 0}
        onClick={() => set([...config.sensors, { id: `T${config.sensors.length + 1}`, type: "temperature", at: points[points.length - 1] ?? "" }])}
      >
        + Sensor
      </button>
    </div>
  );
}

function ComponentResults({ id }: { id: string }) {
  const { conditionId, results } = useWorkspace();
  const r = conditionId ? results[conditionId]?.components[id] : undefined;
  if (!r) return <p className="hint">Run a condition to see this part's loads and checks.</p>;
  return (
    <table>
      <thead>
        <tr><th>Quantity</th><th className="n">Value</th><th className="n">Limit</th><th>Status</th></tr>
      </thead>
      <tbody>
        {Object.entries(r.loads)
          .filter(([, v]) => v.value !== null)
          .map(([k, v]) => (
            <tr key={k}>
              <td>{label(k)} <span className="u muted">({v.unit})</span></td>
              <td className="n">{v.value!.toFixed(v.unit === "%" ? 0 : 1)}</td>
              <td className="n" />
              <td />
            </tr>
          ))}
        {r.checks.map((c) => (
          <tr key={c.name}>
            <td>{label(c.name)} <span className="u muted">({c.unit})</span></td>
            <td className="n">{c.value?.toFixed(1)}</td>
            <td className="n">{c.limit?.toFixed(1)}</td>
            <td>
              <span className={`status ${c.passed ? "pass" : "fail"}`}>
                <StatusIcon kind={c.passed ? "pass" : "fail"} />
                {c.passed ? "OK" : "Over limit"}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function Inspector() {
  const { config, selected, edit, select } = useWorkspace();
  if (!config) return null;
  const comp = selected ? config.components[selected] : undefined;
  if (!selected || !comp) {
    return (
      <div className="stack">
        <h2>Unit settings</h2>
        <ObjectFields node={defOf("UnitInfo")} value={config.unit} onChange={(unit) => edit({ ...config, unit })} />
        <h3>Airflows</h3>
        <ObjectFields node={defOf("Airflows")} value={config.airflows} onChange={(airflows) => edit({ ...config, airflows })} />
        <Sensors />
      </div>
    );
  }
  const def = componentDef(comp as { type: string; mode?: string });
  return (
    <div className="stack">
      <div className="row">
        <h2>{selected} · {COMPONENT_LABELS[comp.type] ?? comp.type}</h2>
      </div>
      {def ? (
        <ObjectFields node={def} value={comp} onChange={(c) => edit({ ...config, components: { ...config.components, [selected]: c } })} />
      ) : (
        <p className="hint">No form for {comp.type}.</p>
      )}
      <h3>This condition</h3>
      <ComponentResults id={selected} />
      <button
        className="btn danger"
        onClick={() => {
          edit(removeComponent(config, selected));
          select(null);
        }}
      >
        Remove {selected}
      </button>
    </div>
  );
}
