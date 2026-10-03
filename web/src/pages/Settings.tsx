import { TopBar } from "../components/TopBar.tsx";
import { useWorkspace } from "../store.ts";

export function SettingsPage() {
  const { units, setUnits } = useWorkspace();
  return (
    <>
      <TopBar crumbs={<><span className="sep">/</span><h1>Settings</h1></>} />
      <main className="main">
        <div className="card stack">
          <label className="field">
            Unit system for display
            <select aria-label="Default unit system" value={units} onChange={(e) => setUnits(e.target.value as "ip" | "si")}>
              <option value="ip">I-P (°F, cfm, Btu/lb)</option>
              <option value="si">SI (°C, m³/s, kJ/kg)</option>
            </select>
          </label>
          <p className="hint">Remembered in this browser.</p>
        </div>
      </main>
    </>
  );
}
