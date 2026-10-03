// State table (TanStack Table v9). Numbers are the API's display values.
import { createColumnHelper, tableFeatures, useTable } from "@tanstack/react-table";
import { useMemo } from "react";
import type { StateRow } from "../api.ts";
import { useWorkspace } from "../store.ts";

const features = tableFeatures({});
const helper = createColumnHelper<typeof features, StateRow>();
const EMPTY: StateRow[] = [];

export function StateTable() {
  const { conditionId, results, hovered, hover } = useWorkspace();
  const result = conditionId ? results[conditionId] : undefined;
  const u = result?.units ?? {};
  const num = (digits: number) => (info: { getValue: () => unknown }) => (info.getValue() as number).toFixed(digits);
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor("key", { header: "Location", cell: (i) => (i.getValue() as string).replace("after:", "after ") }),
        helper.accessor("db", { header: `db (${u.db ?? ""})`, cell: num(1) }),
        helper.accessor("wb", { header: `wb (${u.wb ?? ""})`, cell: num(1) }),
        helper.accessor("rh", { header: "RH (%)", cell: num(0) }),
        helper.accessor("w", { header: `W (${u.w ?? ""})`, cell: num(1) }),
        helper.accessor("h", { header: `h (${u.h ?? ""})`, cell: num(2) }),
        helper.accessor("flow", { header: `Flow (${u.flow ?? ""})`, cell: num(u.flow === "cfm" ? 0 : 3) }),
      ]),
    [u.db, u.wb, u.w, u.h, u.flow],
  );
  const table = useTable({ features, columns, data: result?.states ?? EMPTY });
  if (!result) return <p className="empty">Run a condition to see the states.</p>;
  return (
    <table aria-label="States">
      <thead>
        {table.getHeaderGroups().map((g) => (
          <tr key={g.id}>
            {g.headers.map((h, i) => (
              <th key={h.id} className={i ? "n" : undefined}>
                <table.FlexRender header={h} />
              </th>
            ))}
          </tr>
        ))}
      </thead>
      <tbody>
        {table.getRowModel().rows.map((row) => (
          <tr
            key={row.id}
            className="hoverable"
            aria-selected={hovered === row.original.key}
            onMouseEnter={() => hover(row.original.key)}
            onMouseLeave={() => hover(null)}
          >
            {row.getAllCells().map((c, i) => (
              <td key={c.id} className={i ? "n" : undefined}>
                <table.FlexRender cell={c} />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
