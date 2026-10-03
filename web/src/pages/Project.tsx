import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useApi } from "../api.ts";
import { TopBar } from "../components/TopBar.tsx";
import type { UnitConfig } from "../lib/model.ts";

type ProjectDetail = Awaited<ReturnType<ReturnType<typeof useApi>["getProject"]>>;

export function ProjectPage() {
  const { id = "" } = useParams();
  const api = useApi();
  const nav = useNavigate();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api.getProject(id).then(setProject, (e) => setError(e.message)), [api, id]);
  useEffect(() => {
    load();
  }, [load]);

  const create = async (unitName: string, config?: UnitConfig) => {
    try {
      const u = await api.createUnit(id, unitName, config);
      nav(`/units/${u.id}`);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  // M3-7: import a unit from a JSON file (the same file Export writes).
  const importFile = async (file: File) => {
    try {
      const config = JSON.parse(await file.text()) as UnitConfig;
      await create(config.unit?.name ?? file.name.replace(/\.json$/, ""), config);
    } catch (e) {
      setError(e instanceof SyntaxError ? `${file.name} is not valid JSON.` : (e as Error).message);
    }
  };

  return (
    <>
      <TopBar crumbs={<><span className="sep">/</span><h1>{project?.name ?? "…"}</h1></>} />
      <main className="main">
        <div className="stack">
          {error && <div className="error-box">{error}</div>}
          <div className="row">
            <input aria-label="New unit name" placeholder="New unit name (e.g. AHU-1)" value={name} onChange={(e) => setName(e.target.value)} />
            <button className="btn primary" disabled={!name.trim()} onClick={() => create(name.trim())}>New blank unit</button>
            <label className="btn">
              Import unit JSON…
              <input type="file" accept="application/json,.json" hidden onChange={(e) => e.target.files?.[0] && importFile(e.target.files[0])} />
            </label>
          </div>
          <div className="cards">
            {project?.units.length === 0 && <p className="empty">No units yet.</p>}
            {project?.units.map((u) => (
              <Link key={u.id} to={`/units/${u.id}`} className="list-link">
                <span>{u.name}</span>
                <span className="muted small">version {u.version}</span>
              </Link>
            ))}
          </div>
        </div>
      </main>
    </>
  );
}
