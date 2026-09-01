import { useState } from "react";
import { NavLink } from "react-router-dom";
import { moreToolsGroup, navGroups } from "./navConfig";

function NavGroupBlock({ label, items }: { label: string; items: { label: string; path: string }[] }) {
  return (
    <div className="mb-5">
      <div className="px-3 mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
        {label}
      </div>
      <div className="flex flex-col gap-0.5">
        {items.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `relative px-3 py-1.5 rounded-md text-sm transition-all duration-200 border-l-2 ${
                isActive
                  ? "bg-blue-50 text-blue-700 font-medium border-l-cyan-400 shadow-[0_0_16px_rgba(34,211,238,0.15)]"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 border-l-transparent hover:border-l-slate-300"
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </div>
    </div>
  );
}

export function Sidebar() {
  const [moreOpen, setMoreOpen] = useState(false);

  return (
    <aside className="w-56 shrink-0 h-screen sticky top-0 bg-white border-r border-slate-200 flex flex-col py-5 px-2 overflow-y-auto">
      <div className="px-3 mb-6 flex items-center gap-2">
        <span
          className="h-2 w-2 rounded-full shrink-0"
          style={{ background: "var(--cyan)", boxShadow: "var(--glow-cyan)" }}
        />
        <div>
          <div className="font-display text-[14px] font-bold leading-tight bg-clip-text text-transparent bg-gradient-to-r from-cyan-300 via-sky-300 to-fuchsia-400">
            F5 CONFIG INTEL
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
          className="w-full text-left px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400 hover:text-slate-600"
        >
          {moreToolsGroup.label} {moreOpen ? "▾" : "▸"}
        </button>
        {moreOpen && (
          <div className="px-3 py-2 text-xs text-slate-400">
            No additional tools yet.
          </div>
        )}
      </div>
    </aside>
  );
}
