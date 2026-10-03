// Psychrometric chart (spec §8.3): custom SVG with d3-scale. Every line comes
// from GET /v1/chart-grid; process points are the API's display values (db, W).
import { scaleLinear } from "d3-scale";
import { useEffect, useState } from "react";
import { useApi, type ChartGrid, type ConditionOut } from "../api.ts";
import { useWorkspace } from "../store.ts";

const W = 640, H = 320, M = { l: 40, r: 48, t: 16, b: 40 };

export function processKeys(result: ConditionOut, supply: string[]): string[] {
  const keys = ["oa_intake", ...supply.slice(1).map((t) => `after:${t}`)];
  return keys.filter((k) => result.states.some((s) => s.key === k));
}

const short = (key: string) => (key === "oa_intake" ? "OA" : key === "ra" ? "RA" : key.replace("after:", "").replace(".supply", ""));

export function PsychChart() {
  const api = useApi();
  const { units, pressure, conditionId, results, config, hovered, hover } = useWorkspace();
  const [grid, setGrid] = useState<ChartGrid | null>(null);
  useEffect(() => {
    if (pressure !== null) api.chartGrid(pressure, units).then(setGrid, () => setGrid(null));
  }, [api, pressure, units]);
  const result = conditionId ? results[conditionId] : undefined;
  if (!grid || !config) return <p className="empty">Run a condition to draw the chart (it needs the site pressure from the engine).</p>;
  const x = scaleLinear().domain([grid.x.min, grid.x.max]).range([M.l, W - M.r]);
  const y = scaleLinear().domain([grid.y.min, grid.y.max]).range([H - M.b, M.t]);
  const path = (pts: [number, number][]) => pts.map(([a, b], i) => `${i ? "L" : "M"}${x(a).toFixed(1)} ${y(b).toFixed(1)}`).join(" ");
  const pt = (key: string) => result?.states.find((s) => s.key === key);
  const proc = result ? processKeys(result, config.lanes.supply).map((k) => pt(k)!) : [];
  const box = Object.entries(config.components).find(([, c]) => c.type === "mixing_box")?.[0];
  const ra = pt("ra"), mixed = box ? pt(`after:${box}`) : undefined;
  return (
    <svg className="psych" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Psychrometric chart">
      {grid.lines.map((ln, i) => (
        <path key={i} className={ln.kind === "saturation" ? "saturation" : `grid ${ln.kind}`} d={path(ln.points)} />
      ))}
      {x.ticks(8).map((v) => (
        <text key={`x${v}`} className="axis" x={x(v)} y={H - M.b + 14} textAnchor="middle">{v}</text>
      ))}
      {y.ticks(5).map((v) => (
        <text key={`y${v}`} className="axis" x={W - M.r + 6} y={y(v) + 4}>{v}</text>
      ))}
      <text className="axis-title" x={(M.l + W - M.r) / 2} y={H - 6} textAnchor="middle">{grid.x.label}</text>
      <text className="axis-title" x={W - M.r - 4} y={M.t - 4} textAnchor="end">{grid.y.label}</text>
      {proc.length > 1 && <path className="process" d={path(proc.map((s) => [s.db, s.w]))} />}
      {ra && mixed && <path className="process recirc" d={path([[ra.db, ra.w], [mixed.db, mixed.w]])} />}
      {[...proc, ...(ra ? [ra] : [])].map((s) => (
        <g key={s.key} onMouseEnter={() => hover(s.key)} onMouseLeave={() => hover(null)}>
          <circle className={`state${hovered === s.key ? " hovered" : ""}`} cx={x(s.db)} cy={y(s.w)} r={4}>
            <title>{`${short(s.key)}: ${s.db.toFixed(1)} ${result!.units.db}, ${s.w.toFixed(1)} ${result!.units.w}`}</title>
          </circle>
          {(hovered === s.key || ["OA", "RA"].includes(short(s.key))) && (
            <text className="state-label" x={x(s.db) + 7} y={y(s.w) - 7}>{short(s.key)}</text>
          )}
        </g>
      ))}
    </svg>
  );
}
