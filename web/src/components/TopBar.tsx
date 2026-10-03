import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useAuthToken } from "../auth.tsx";

export function TopBar(props: { crumbs?: ReactNode; children?: ReactNode }) {
  const { userButton } = useAuthToken();
  return (
    <header className="topbar">
      <div className="crumbs">
        <Link to="/projects" className="muted small">Projects</Link>
        {props.crumbs}
      </div>
      {props.children}
      <div className="spacer" />
      <Link to="/settings" className="small">Settings</Link>
      {userButton}
    </header>
  );
}

export function StatusIcon({ kind }: { kind: "pass" | "warning" | "fail" }) {
  return (
    <svg className="icon" aria-hidden="true">
      <use href={`#status-${kind}`} />
    </svg>
  );
}
