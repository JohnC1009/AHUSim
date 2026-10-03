import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useApi, type ProjectOut } from "../api.ts";
import { TopBar } from "../components/TopBar.tsx";

export function ProjectsPage() {
  const api = useApi();
  const nav = useNavigate();
  const [projects, setProjects] = useState<ProjectOut[] | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.listProjects().then(setProjects, (e) => setError(e.message));
  }, [api]);
  const create = async () => {
    try {
      const p = await api.createProject(name.trim());
      nav(`/projects/${p.id}`);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <>
      <TopBar />
      <main className="main">
        <div className="stack">
          <h1>Projects</h1>
          {error && <div className="error-box">{error}</div>}
          <div className="row">
            <input aria-label="New project name" placeholder="New project name" value={name} onChange={(e) => setName(e.target.value)} />
            <button className="btn primary" disabled={!name.trim()} onClick={create}>Create project</button>
          </div>
          <div className="cards">
            {projects?.length === 0 && <p className="empty">No projects yet.</p>}
            {projects?.map((p) => (
              <Link key={p.id} to={`/projects/${p.id}`} className="list-link">
                <span>{p.name}</span>
                <span className="muted small">{new Date(p.updated_at).toLocaleDateString()}</span>
              </Link>
            ))}
          </div>
        </div>
      </main>
    </>
  );
}
