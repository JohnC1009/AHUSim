// Lane-constrained schematic (spec §8.2): supply lane above, return lane below
// drawn right-to-left, parts in both lanes spanning them. No free wiring:
// "+" slots between parts are the only places to add one.
import { Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import { useMemo } from "react";
import type { ConditionOut } from "../api.ts";
import * as t from "../design/tokens.ts";
import { componentOf, layout, typeOf } from "../lib/lanes.ts";
import { SYMBOL, type UnitConfig } from "../lib/model.ts";
import { useWorkspace } from "../store.ts";

const COL = t.layout.symbol * 2.5;
const ROW = { supply: 0, return: t.layout.symbol * 5 };
const HANDLE = { opacity: 0, width: 1, height: 1, minWidth: 0, minHeight: 0, border: 0 };

type CompData = { id: string; symbol: string; state?: string; selected: boolean; failing: boolean; hovered: boolean; lane: string };

function Handles({ lane }: { lane: string }) {
  const [inPos, outPos] = lane === "return" ? [Position.Right, Position.Left] : [Position.Left, Position.Right];
  return (
    <>
      <Handle type="target" position={inPos} style={HANDLE} />
      <Handle type="source" position={outPos} style={HANDLE} />
    </>
  );
}

function CompNode({ data }: NodeProps<Node<CompData>>) {
  const cls = ["flow-node", data.selected && "selected", data.failing && "failing", data.hovered && "hovered"].filter(Boolean).join(" ");
  return (
    <div className={cls} data-testid={`node-${data.id}`}>
      <span className="id">{data.id}</span>
      <svg className="sym-box" aria-hidden="true"><use href={`#sym-${data.symbol}`} /></svg>
      {data.state && <span className="state">{data.state}</span>}
      <Handles lane={data.lane} />
    </div>
  );
}

function AnchorNode({ data }: NodeProps<Node<{ lane: string; label?: string; state?: string }>>) {
  return (
    <div className="flow-boundary">
      {data.label}
      {data.state && <div className="flow-node"><span className="state">{data.state}</span></div>}
      <Handles lane={data.lane} />
    </div>
  );
}

function SharedNode({ data }: NodeProps<Node<CompData & { height: number }>>) {
  const cls = ["flow-node", data.selected && "selected", data.failing && "failing"].filter(Boolean).join(" ");
  return (
    <div className={`${cls} flow-shared`} data-testid={`node-${data.id}`} style={{ height: data.height }}>
      <span className="id">{data.id}</span>
      <svg className="sym-box" aria-hidden="true"><use href={`#sym-${data.symbol}`} /></svg>
    </div>
  );
}

function SlotNode({ data }: NodeProps<Node<{ lane: string; index: number; picked: boolean }>>) {
  return (
    <div className={`flow-slot${data.picked ? " picked" : ""}`} data-testid={`slot-${data.lane}-${data.index}`} title="Add a component here">
      +
    </div>
  );
}

const nodeTypes = { comp: CompNode, anchor: AnchorNode, shared: SharedNode, slot: SlotNode };

function stateLabel(result: ConditionOut | undefined, token: string): string | undefined {
  const s = result?.states.find((x) => x.key === `after:${token}`);
  if (!s) return undefined;
  return `${s.db.toFixed(1)} ${result!.units.db} · ${s.rh.toFixed(0)} %`;
}

export function buildFlow(
  cfg: UnitConfig,
  result: ConditionOut | undefined,
  selected: string | null,
  slot: { supply: number | null; ret: number | null },
  hovered: string | null,
) {
  const placed = layout(cfg);
  const failing = new Set((result?.failures ?? []).map((f) => (f.component ?? "").split(".")[0]));
  const nodes: Node[] = [];
  const at = new Map<string, { x: number; lane: string }>(); // "<lane>:<token>" -> position
  const half = t.layout.symbol / 2;
  for (const p of placed) {
    const x = p.column * COL;
    if (p.lane === "both") {
      const id = p.token;
      nodes.push({
        id: `shared:${id}`, type: "shared", position: { x, y: ROW.supply - half }, draggable: false,
        data: { id, symbol: SYMBOL[cfg.components[id].type] ?? "coil", selected: selected === id, failing: failing.has(id), hovered: false, lane: "both",
                height: ROW.return - ROW.supply + t.layout.symbol * 2 },
      });
      continue;
    }
    at.set(`${p.lane}:${p.token}`, { x, lane: p.lane });
    const nodeId = `${p.lane}:${p.token}`;
    const y = ROW[p.lane];
    const comp = componentOf(p.token);
    const shared = p.token !== "oa" && p.token !== "ra" && (p.token.includes(".") || typeOf(cfg, p.token) === "mixing_box");
    if (p.token === "oa" || p.token === "ra" || shared) {
      // Anchors for shared parts sit at the right edge of the tall node, so the
      // duct-state label after them is not hidden behind it.
      const ax = shared ? x + t.layout.symbol + t.space[1] : x;
      nodes.push({
        id: nodeId, type: "anchor", position: { x: ax, y: y + half }, draggable: false,
        data: { lane: p.lane, label: p.token === "oa" ? "OA" : p.token === "ra" ? "RA" : undefined,
                state: shared ? stateLabel(result, p.lane === "return" && typeOf(cfg, p.token) === "mixing_box" ? `${p.token}.relief` : p.token) : undefined },
      });
    } else {
      nodes.push({
        id: nodeId, type: "comp", position: { x, y }, draggable: false,
        data: { id: comp, symbol: SYMBOL[typeOf(cfg, p.token) ?? ""] ?? "coil", state: stateLabel(result, p.token),
                selected: selected === comp, failing: failing.has(comp), hovered: hovered === `after:${p.token}`, lane: p.lane },
      });
    }
  }
  const edges: Edge[] = [];
  const lanes = { supply: cfg.lanes.supply, return: cfg.lanes.return } as const;
  for (const lane of ["supply", "return"] as const) {
    const tokens = lanes[lane];
    const pick = lane === "supply" ? slot.supply : slot.ret;
    for (let k = 0; k < tokens.length; k++) {
      const here = at.get(`${lane}:${tokens[k]}`)!;
      const next = k + 1 < tokens.length ? at.get(`${lane}:${tokens[k + 1]}`)! : null;
      if (next) edges.push({ id: `e:${lane}:${k}`, source: `${lane}:${tokens[k]}`, target: `${lane}:${tokens[k + 1]}`, type: "straight" });
      const dir = lane === "supply" ? 1 : -1;
      const sx = next ? (here.x + next.x) / 2 : here.x + (dir * COL) / 2;
      nodes.push({
        id: `slot:${lane}:${k + 1}`, type: "slot", draggable: false,
        position: { x: sx + half - t.space[3], y: ROW[lane] - t.space[8] },
        data: { lane, index: k + 1, picked: pick === k + 1 },
      });
    }
  }
  return { nodes, edges };
}

export function Schematic() {
  const { config, selected, slot, hovered, conditionId, results, select, pickSlot } = useWorkspace();
  const result = conditionId ? results[conditionId] : undefined;
  const flow = useMemo(() => (config ? buildFlow(config, result, selected, slot, hovered) : { nodes: [], edges: [] }), [config, result, selected, slot, hovered]);
  if (!config) return null;
  return (
    <div className="schematic-flow" aria-label="Schematic">
      <ReactFlow
        key={flow.nodes.length /* re-fit the view whenever parts are added or removed */}
        nodes={flow.nodes}
        edges={flow.edges}
        nodeTypes={nodeTypes}
        nodesDraggable={false}
        nodesConnectable={false}
        fitView
        onNodeClick={(_, n) => {
          if (n.type === "slot") pickSlot(n.data.lane === "supply" ? "supply" : "ret", n.data.index as number);
          else if (n.type === "comp" || n.type === "shared") select(n.data.id as string);
        }}
        onPaneClick={() => select(null)}
      />
    </div>
  );
}
