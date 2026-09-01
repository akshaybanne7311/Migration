import type { ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { ThemeToggle } from "../components/ThemeToggle";
import { useSessionsList, useSessionStore, useValidatedSession } from "../api/queries";

function SessionPicker() {
  const { data: sessions } = useSessionsList();
  const { sessionId, session } = useValidatedSession();
  const setCurrentSessionId = useSessionStore((s) => s.setCurrentSessionId);

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-400">Session</span>
      <select
        className="text-sm border border-slate-200 rounded-md px-2 py-1.5 bg-white text-slate-700 min-w-[220px] outline-none focus:border-slate-300 focus:shadow-[0_0_0_3px_rgba(34,211,238,0.15)] transition-shadow"
        value={sessionId ?? ""}
        onChange={(e) => setCurrentSessionId(e.target.value || null)}
      >
        <option value="">No session selected</option>
        {(sessions ?? []).map((s) => (
          <option key={s.id} value={s.id} disabled={s.status !== "ready"}>
            {s.name} {s.status !== "ready" ? `(${s.status})` : ""}
          </option>
        ))}
      </select>
      {session && (
        <span className="text-xs text-slate-400">
          {session.vip_count} VIPs · {session.pool_count} Pools · {session.node_count} Nodes ·{" "}
          {session.vlan_count} VLANs
        </span>
      )}
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex bg-slate-50 text-slate-900">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 shrink-0 border-b border-slate-200 bg-white flex items-center justify-between px-6 relative">
          <SessionPicker />
          <ThemeToggle />
          <div
            className="absolute left-0 right-0 bottom-0 h-px"
            style={{ background: "linear-gradient(90deg, transparent, rgba(34,211,238,0.5), transparent)" }}
          />
        </header>
        <main className="flex-1 min-w-0 p-6">
          <div className="animate-page-in">{children}</div>
        </main>
      </div>
    </div>
  );
}
