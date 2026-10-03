import { FailureStrip } from "../components/FailureStrip.tsx";
import { Inspector } from "../components/Inspector.tsx";
import { Palette } from "../components/Palette.tsx";
import { PsychChart } from "../components/PsychChart.tsx";
import { Schematic } from "../components/Schematic.tsx";
import { StateTable } from "../components/StateTable.tsx";
import { useWorkspace } from "../store.ts";

export function Workspace() {
  const { config, conditionId, results } = useWorkspace();
  const active = conditionId ? results[conditionId]?.mode : undefined;
  return (
    <div className="workspace">
      <aside className="panel left stack bp-editor-only">
        <Palette />
        <div className="stack tight">
          <h3>Modes</h3>
          {config?.sequence.modes.length === 0 && <p className="hint">No modes yet (Sequence tab).</p>}
          <ul className="list">
            {[...(config?.sequence.modes ?? [])]
              .sort((a, b) => a.priority - b.priority)
              .map((m) => (
                <li key={m.id} aria-selected={m.id === active}>
                  <span className="badge num">{m.priority}</span>
                  {m.id}
                </li>
              ))}
          </ul>
        </div>
      </aside>
      <main className="canvas">
        <div className="row">
          <h2>Schematic</h2>
          <span className="lane-caption">Supply lane above (left → right), return lane below (right → left). Click + to choose where a part goes.</span>
        </div>
        <Schematic />
      </main>
      <aside className="panel right stack bp-tablet-up">
        <Inspector />
      </aside>
      <FailureStrip />
      <div className="dock">
        <section>
          <div className="dock-head"><h2>Psychrometric chart</h2></div>
          <PsychChart />
        </section>
        <section>
          <div className="dock-head"><h2>States</h2><span className="small muted">Hover a row to find it on the chart and schematic</span></div>
          <StateTable />
        </section>
      </div>
    </div>
  );
}
