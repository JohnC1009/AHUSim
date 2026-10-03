import { useNavigate } from "react-router-dom";
import { StatusIcon } from "../components/TopBar.tsx";
import { useWorkspace } from "../store.ts";

export function ResultsPage() {
  const { config, results, setCondition, unitId } = useWorkspace();
  const nav = useNavigate();
  const list = config?.conditions.operating ?? [];
  if (list.length === 0) return <p className="empty">Add an operating condition, then Run.</p>;
  return (
    <main className="main">
      <div className="card stack">
        <h2>Scenario results</h2>
        <table aria-label="Scenario results">
          <thead><tr><th>Condition</th><th>Mode</th><th>Result</th><th className="n">Failures</th><th>First failure</th></tr></thead>
          <tbody>
            {list.map((c) => {
              const r = results[c.id];
              const fails = r?.failures.filter((f) => f.severity === "error") ?? [];
              const ok = r && r.valid && fails.length === 0;
              return (
                <tr key={c.id} className="hoverable" onClick={() => { setCondition(c.id); nav(`/units/${unitId}`); }}>
                  <td>{c.id}</td>
                  <td>{r ? (r.mode ?? "—") : ""}</td>
                  <td>
                    {r ? (
                      <span className={`status ${ok ? "pass" : "fail"}`}><StatusIcon kind={ok ? "pass" : "fail"} />{ok ? "Pass" : "Fail"}</span>
                    ) : <span className="muted small">not run</span>}
                  </td>
                  <td className="n">{r ? fails.length : ""}</td>
                  <td>{fails[0]?.message ?? ""}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="hint">Sweeps and annual runs arrive in M4.</p>
      </div>
    </main>
  );
}
