import { useWorkspace } from "../store.ts";
import { downloadJson } from "./UnitLayout.tsx";

export function ExportPage() {
  const { config } = useWorkspace();
  if (!config) return null;
  return (
    <main className="main">
      <div className="card stack">
        <h2>Export</h2>
        <p>Download this unit as JSON (the same file Import accepts on the project page).</p>
        <div className="row"><button className="btn primary" onClick={() => downloadJson(config.unit.name, config)}>Download unit JSON</button></div>
        <p className="hint">The 23 09 93 sequence document (.docx, Markdown, points list) arrives in M6.</p>
      </div>
    </main>
  );
}
