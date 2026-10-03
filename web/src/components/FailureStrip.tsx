import type { FailureOut } from "../api.ts";
import { StatusIcon } from "./TopBar.tsx";
import { useWorkspace } from "../store.ts";

const KIND_LABEL: Record<string, string> = {
  setpoint_not_met: "Setpoint not met", limit_exceeded: "Limit exceeded", mode_gap: "Mode gap",
  mode_overlap: "Mode overlap", config_error: "Configuration", fighting: "Fighting", cannot_compute: "Cannot compute",
  non_monotonic: "Non-monotonic", non_converged: "Not converged", engine_residual: "Engine residual",
};

export function failuresInView(staticFailures: FailureOut[], current: FailureOut[]): FailureOut[] {
  const seen = new Set<string>();
  return [...current, ...staticFailures].filter((f) => !seen.has(f.message) && !!seen.add(f.message));
}

export function FailureStrip() {
  const { staticFailures, conditionId, results, select } = useWorkspace();
  const list = failuresInView(staticFailures, conditionId ? (results[conditionId]?.failures ?? []) : []);
  return (
    <section className="failure-strip" aria-label="Failures">
      {list.length === 0 ? (
        <p className="empty">No failures{conditionId && results[conditionId] ? " at this condition" : ""}.</p>
      ) : (
        <ul className="list">
          {list.map((f, i) => {
            const status = f.severity === "warning" ? "warning" : "fail";
            return (
              <li key={i} className="clickable" onClick={() => f.component && select(f.component.split(".")[0])}>
                <span className={`status ${status} kind`}>
                  <StatusIcon kind={status} />
                  {KIND_LABEL[f.kind] ?? f.kind}
                </span>
                <span className="where">{[f.mode, f.condition_id, f.component].filter(Boolean).join(" · ")}</span>
                <span>{f.message}</span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
