import { useState } from "react";
import { NavLink } from "react-router-dom";
import type { LucideIcon } from "lucide-react";
import { ChevronRight, FileDown, ShieldCheck } from "lucide-react";
import { moreToolsGroup, navGroups } from "./navConfig";
import { useBackendHealth } from "../api/queries";
import { CSV_TEMPLATES, downloadCsvTemplate } from "../utils/csvTemplates";
import type { CsvImportType } from "../api/types";

function NavGroupBlock({ label, items }: { label: string; items: { label: string; path: string; icon: LucideIcon }[] }) {
  return (
    <div className="mb-5">
      <div className="px-3 mb-1.5 flex items-center gap-1.5">
        <span className="h-[3px] w-[3px] rounded-full" style={{ background: "var(--border-strong)" }} />
        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">{label}</span>
      </div>
      <div className="flex flex-col gap-0.5">
        {items.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `group relative flex items-center gap-2.5 px-3 py-1.5 rounded-md text-sm transition-all duration-200 border-l-2 ${
                isActive
                  ? "bg-blue-50 text-blue-700 font-medium"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 border-l-transparent hover:border-l-slate-300 hover:translate-x-0.5"
              }`
            }
            style={({ isActive }) =>
              isActive
                ? { borderLeftColor: "var(--cyan)", boxShadow: "0 0 16px color-mix(in srgb, var(--cyan) 18%, transparent)" }
                : undefined
            }
          >
            {({ isActive }) => (
              <>
                <item.icon
                  size={15}
                  strokeWidth={2}
                  className="shrink-0 transition-colors"
                  style={{ color: isActive ? "var(--cyan-bright)" : undefined }}
                />
                <span>{item.label}</span>
                {isActive && (
                  <span
                    className="neon-dot ml-auto"
                    style={{ background: "var(--cyan)" }}
                  />
                )}
              </>
            )}
          </NavLink>
        ))}
      </div>
    </div>
  );
}

function BackendStatus() {
  const { data, isError, isLoading } = useBackendHealth();
  const connected = !!data && !isError;
  const label = isLoading ? "Checking…" : connected ? "Backend connected" : "Backend unreachable";
  const dotColor = isLoading ? "var(--text-dim)" : connected ? "var(--success)" : "var(--danger)";
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 text-xs text-slate-500">
      <span
        className={connected ? "neon-dot" : "h-1.5 w-1.5 rounded-full shrink-0"}
        style={{ background: dotColor }}
      />
      <span>{label}</span>
      {data?.version && <span className="text-slate-400">· v{data.version}</span>}
    </div>
  );
}

function QuickTools() {
  return (
    <div className="px-3 py-1.5">
      <div className="text-[10px] uppercase tracking-wider text-slate-400 mb-1.5">Diagnostics</div>
      <NavLink
        to="/health-check"
        className="flex items-center gap-2 text-left text-xs text-slate-600 hover:text-slate-900 rounded px-1.5 py-1 hover:bg-slate-100 transition-colors"
        title="Run heuristic config checks against the current session — the same spirit as what F5 TAC uses iHealth for"
      >
        <ShieldCheck size={13} className="shrink-0 text-slate-400" />
        Config Health Check
      </NavLink>
    </div>
  );
}

function CsvTemplateLinks() {
  return (
    <div className="px-3 py-1.5">
      <div className="text-[10px] uppercase tracking-wider text-slate-400 mb-1.5">CSV templates</div>
      <div className="flex flex-col gap-0.5">
        {(Object.keys(CSV_TEMPLATES) as CsvImportType[]).map((key) => (
          <button
            key={key}
            onClick={() => downloadCsvTemplate(key)}
            className="flex items-center gap-2 text-left text-xs text-slate-600 hover:text-slate-900 rounded px-1.5 py-1 hover:bg-slate-100 transition-colors"
            title={CSV_TEMPLATES[key].hint}
          >
            <FileDown size={13} className="shrink-0 text-slate-400" />
            {CSV_TEMPLATES[key].label}
          </button>
        ))}
      </div>
    </div>
  );
}

export function Sidebar() {
  const [moreOpen, setMoreOpen] = useState(false);

  return (
    <aside
      className="relative w-56 shrink-0 h-screen sticky top-0 bg-white flex flex-col py-5 px-2 overflow-y-auto"
      style={{
        backgroundImage:
          "linear-gradient(180deg, color-mix(in srgb, var(--cyan) 4%, transparent), transparent 30%)",
        borderRight: "1px solid var(--border-soft)",
      }}
    >
      <div
        className="pointer-events-none absolute right-0 top-0 bottom-0 w-px"
        style={{ background: "linear-gradient(180deg, transparent, var(--border-strong), transparent)" }}
      />

      <div className="px-3 mb-6 flex items-center gap-2">
        <span
          className="h-2 w-2 rounded-full shrink-0"
          style={{ background: "var(--cyan)", boxShadow: "var(--glow-cyan)" }}
        />
        <div>
          <div
            className="animate-gradient-text font-display text-[12.5px] font-bold leading-tight tracking-tight whitespace-nowrap bg-clip-text text-transparent"
            style={{ backgroundImage: "linear-gradient(90deg, var(--cyan-bright), var(--violet), var(--magenta))" }}
          >
            CONFIG INTELLIGENCE
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5 tracking-wide">Migration workspace</div>
        </div>
      </div>

      {navGroups.map((group) => (
        <NavGroupBlock key={group.label} label={group.label} items={group.items} />
      ))}

      <div className="mt-auto">
        <button
          onClick={() => setMoreOpen((v) => !v)}
          className="w-full flex items-center gap-1.5 text-left px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400 hover:text-slate-600"
        >
          <ChevronRight size={12} className="transition-transform" style={{ transform: moreOpen ? "rotate(90deg)" : "rotate(0deg)" }} />
          {moreToolsGroup.label}
        </button>
        {moreOpen && (
          <div className="animate-page-in border-t mt-1 pt-1" style={{ borderColor: "var(--border-faint)" }}>
            <QuickTools />
            <CsvTemplateLinks />
            <BackendStatus />
          </div>
        )}
      </div>
    </aside>
  );
}
