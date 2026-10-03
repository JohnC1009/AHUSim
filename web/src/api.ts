// Typed calls to the API. Every request carries the Clerk session token.
// Errors come back as one plain sentence ({"message": ...}).
import { useMemo } from "react";
import { useAuthToken } from "./auth.tsx";
import type { OperatingCondition, UnitConfig, UnitSystem } from "./lib/model.ts";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {}

export type FailureOut = {
  kind: string;
  severity: "error" | "warning";
  message: string;
  component: string | null;
  mode: string | null;
  condition_id: string | null;
};
export type StateRow = { key: string; db: number; wb: number; dp: number; rh: number; w: number; h: number; v: number; flow: number };
export type CheckOut = { name: string; value: number | null; limit: number | null; unit: string; passed: boolean };
export type ComponentOut = { loads: Record<string, { value: number | null; unit: string }>; checks: CheckOut[] };
export type ConditionOut = {
  condition_id: string;
  mode: string | null;
  units: Record<string, string>;
  valid: boolean;
  positions: Record<string, number>;
  states: StateRow[];
  components: Record<string, ComponentOut>;
  failures: FailureOut[];
};
export type ScenarioOut = { p: number; static: FailureOut[]; results: ConditionOut[] };
export type ChartGrid = {
  units: UnitSystem;
  x: { min: number; max: number; step: number; label: string };
  y: { min: number; max: number; step: number; label: string };
  lines: { kind: string; label: string; points: [number, number][] }[];
};
export type ProjectOut = { id: string; name: string; updated_at: string };
export type UnitOut = { id: string; name: string; project_id: string; version: number; config: UnitConfig };

export async function errorMessage(r: Response): Promise<string> {
  try {
    const body = await r.json();
    return typeof body.message === "string" ? body.message : `Request failed (${r.status}).`;
  } catch {
    return `Request failed (${r.status}).`;
  }
}

export function useApi() {
  const { getToken } = useAuthToken();
  return useMemo(() => {
    async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
      const token = await getToken();
      const r = await fetch(`${BASE}${path}`, {
        method,
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        },
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
      if (!r.ok) throw new ApiError(await errorMessage(r));
      return (r.status === 204 ? undefined : await r.json()) as T;
    }
    return {
      listProjects: () => call<ProjectOut[]>("GET", "/v1/projects"),
      createProject: (name: string) => call<ProjectOut>("POST", "/v1/projects", { name }),
      getProject: (id: string) =>
        call<ProjectOut & { units: { id: string; name: string; version: number }[] }>("GET", `/v1/projects/${id}`),
      renameProject: (id: string, name: string) => call<ProjectOut>("PATCH", `/v1/projects/${id}`, { name }),
      deleteProject: (id: string) => call<void>("DELETE", `/v1/projects/${id}`),
      createUnit: (projectId: string, name: string, config?: UnitConfig) =>
        call<{ id: string }>("POST", `/v1/projects/${projectId}/units`, { name, config }),
      getUnit: (id: string) => call<UnitOut>("GET", `/v1/units/${id}`),
      saveVersion: (id: string, config: UnitConfig) => call<{ version: number }>("POST", `/v1/units/${id}/versions`, { config }),
      scenario: (config: UnitConfig, conditions: OperatingCondition[], units: UnitSystem) =>
        call<ScenarioOut>("POST", "/v1/scenario", { config, conditions, units }),
      solve: (config: UnitConfig, condition: OperatingCondition, units: UnitSystem) =>
        call<{ p: number; static: FailureOut[]; result: ConditionOut }>("POST", "/v1/solve", { config, condition, units }),
      checks: (config: UnitConfig) => call<{ failures: FailureOut[] }>("POST", "/v1/checks", { config }),
      chartGrid: (p: number, units: UnitSystem) =>
        call<ChartGrid>("GET", `/v1/chart-grid?p=${encodeURIComponent(p)}&units=${units}`),
      schema: () => call<Record<string, unknown>>("GET", "/v1/schema"),
    };
  }, [getToken]);
}
export type Api = ReturnType<typeof useApi>;
