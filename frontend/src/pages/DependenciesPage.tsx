import { useMemo, useState } from "react";
import { useValidatedSession, useVipDependencyGraph, useVips } from "../api/queries";
import { DependencyGraphView } from "../components/DependencyGraphView";
import { Card, EmptyState, PageHeader } from "../components/ui";

export function DependenciesPage() {
  const { sessionId } = useValidatedSession();
  const [search, setSearch] = useState("");
  const { data: vipsData, isLoading: vipsLoading } = useVips(sessionId, search);
  const [selectedVip, setSelectedVip] = useState<string | null>(null);
  const { data: graph, isLoading: graphLoading, isError } = useVipDependencyGraph(sessionId, selectedVip);

  const items = useMemo(() => vipsData?.items ?? [], [vipsData]);

  if (!sessionId) {
    return (
      <div>
        <PageHeader title="Dependencies" />
        <EmptyState title="No session selected" subtitle="Pick a session from the top bar first." />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Dependencies"
        subtitle="Visual topology for one virtual server at a time -- pool, its real members, VLANs, monitors, and profiles, built from the same dependency graph Smart Migration uses to compute what's affected by a change."
      />

      <div className="flex gap-4 items-start">
        <Card className="p-3 w-72 shrink-0">
          <input
            type="text"
            placeholder="Search VIPs…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full text-sm border border-slate-300 rounded-md px-2 py-1.5 mb-2"
          />
          <div className="overflow-auto" style={{ maxHeight: 560 }}>
            {vipsLoading && <div className="text-xs text-slate-400 px-1 py-2">Loading…</div>}
            {!vipsLoading && items.length === 0 && <div className="text-xs text-slate-400 px-1 py-2">No VIPs match.</div>}
            {items.map((v) => (
              <button
                key={v.name}
                onClick={() => setSelectedVip(v.name)}
                className={`w-full text-left text-xs px-2 py-1.5 rounded-md truncate ${
                  selectedVip === v.name ? "bg-blue-50 text-blue-700 font-medium" : "text-slate-600 hover:bg-slate-100"
                }`}
                title={v.name}
              >
                {v.name.replace("/Common/", "")}
              </button>
            ))}
          </div>
        </Card>

        <div className="flex-1 min-w-0">
          {!selectedVip && (
            <EmptyState title="Pick a VIP" subtitle="Select a virtual server on the left to see its full dependency chain." />
          )}
          {selectedVip && graphLoading && <div className="text-sm text-slate-400">Loading graph…</div>}
          {selectedVip && isError && <EmptyState title="Couldn't load this VIP's graph" subtitle="It may have been removed from the session." />}
          {selectedVip && graph && (
            <>
              <div className="mb-3 flex flex-wrap gap-3 text-xs text-slate-500">
                <span>{graph.pools.length} pool{graph.pools.length === 1 ? "" : "s"}</span>
                <span>{graph.nodes.length} node{graph.nodes.length === 1 ? "" : "s"}</span>
                <span>{graph.vlans.length} VLAN{graph.vlans.length === 1 ? "" : "s"}</span>
                <span>{graph.monitors.length} monitor{graph.monitors.length === 1 ? "" : "s"}</span>
                <span>{graph.profiles.length} profile{graph.profiles.length === 1 ? "" : "s"}</span>
              </div>
              <DependencyGraphView graph={graph} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
