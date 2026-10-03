import { useEffect } from "react";
import { NavLink, Outlet, useParams } from "react-router-dom";
import { useApi } from "../api.ts";
import { TopBar } from "../components/TopBar.tsx";
import { useWorkspace } from "../store.ts";

/** Downloads the unit exactly as saved/edited (M3-7). */
export function downloadJson(name: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${name}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
}

const NO_CONDITIONS: never[] = []; // stable fallback so effects do not re-run every render

export function UnitLayout() {
  const { id = "" } = useParams();
  const api = useApi();
  const ws = useWorkspace();
  const { config, units, conditionId, dirty } = ws;
  const conditions = config?.conditions.operating ?? NO_CONDITIONS;
  const current = ws.conditionId ? ws.results[ws.conditionId] : undefined;

  useEffect(() => {
    api.getUnit(id).then(
      (u) => useWorkspace.getState().load(u.id, u.config, u.version),
      (e) => useWorkspace.getState().setError(e.message),
    );
  }, [api, id]);

  // Re-solve the selected condition 300 ms after an edit (spec §8.2); with no
  // condition, refresh the static checks instead.
  useEffect(() => {
    if (!config) return;
    const cond = conditions.find((c) => c.id === conditionId);
    const t = setTimeout(() => {
      const s = useWorkspace.getState();
      if (cond) {
        api.solve(config, cond, units).then((r) => s.setResult(r.result, r.static, r.p), (e) => s.setError(e.message));
      } else {
        api.checks(config).then((r) => useWorkspace.setState({ staticFailures: r.failures }), (e) => s.setError(e.message));
      }
    }, 300);
    return () => clearTimeout(t);
  }, [api, config, conditions, conditionId, units]);

  const runAll = () => {
    if (!config || conditions.length === 0) return;
    api.scenario(config, conditions, units).then(
      (r) => useWorkspace.getState().setResults(r.results, r.static, r.p),
      (e) => useWorkspace.getState().setError(e.message),
    );
  };
  const save = () => {
    if (!config) return;
    api.saveVersion(id, config).then(
      (r) => useWorkspace.getState().saved(r.version),
      (e) => useWorkspace.getState().setError(e.message),
    );
  };

  if (!config) return <p className="page-message">{ws.error ?? "Loading unit…"}</p>;
  return (
    <>
      <TopBar
        crumbs={
          <>
            <span className="sep">/</span>
            <h1>{config.unit.name}</h1>
            <span className="muted small">v{ws.version}</span>
            {dirty && <span className="dirty-dot">unsaved</span>}
          </>
        }
      >
        <nav className="tabs">
          <NavLink to={`/units/${id}`} end>Unit</NavLink>
          <NavLink to="sequence">Sequence</NavLink>
          <NavLink to="conditions">Conditions</NavLink>
          <NavLink to="results">Results</NavLink>
          <NavLink to="export">Export</NavLink>
        </nav>
        <label className="row small muted">
          Condition
          <select aria-label="Condition" value={conditionId ?? ""} onChange={(e) => ws.setCondition(e.target.value || null)}>
            <option value="">— none —</option>
            {conditions.map((c) => (
              <option key={c.id} value={c.id}>{c.id}</option>
            ))}
          </select>
        </label>
        <span className="badge" title="Active mode at this condition">mode: {current?.mode ?? "—"}</span>
        <button className="btn primary" onClick={runAll} disabled={conditions.length === 0}>Run</button>
        <div className="segmented" role="group" aria-label="Unit system">
          <span role="button" aria-pressed={units === "ip"} onClick={() => ws.setUnits("ip")}>I-P</span>
          <span role="button" aria-pressed={units === "si"} onClick={() => ws.setUnits("si")}>SI</span>
        </div>
        <button className="btn" onClick={save} disabled={!dirty}>Save</button>
        <button className="btn" onClick={() => downloadJson(config.unit.name, config)}>Export JSON</button>
      </TopBar>
      <div className="bp-readonly-note">Read-only on screens narrower than 1024 px.</div>
      {ws.error && <div className="error-box">{ws.error}</div>}
      <Outlet />
    </>
  );
}
