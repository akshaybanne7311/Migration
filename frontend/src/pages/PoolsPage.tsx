import { useState } from "react";
import { useNodes, usePools, useValidatedSession } from "../api/queries";
import type { Pool } from "../api/types";
import { Card, EmptyState, PageHeader } from "../components/ui";

export function PoolsPage() {
  const { sessionId } = useValidatedSession();
  const { data, isLoading } = usePools(sessionId);
  const { data: nodesData } = useNodes(sessionId);
  const [expanded, setExpanded] = useState<Pool | null>(null);

  const nodesByName = Object.fromEntries((nodesData?.items ?? []).map((n) => [n.name, n]));

  if (!sessionId) {
    return (
      <div>
        <PageHeader title="Pools" />
        <EmptyState title="No session selected" />
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Pools" subtitle={`${data?.total ?? 0} pools`} />
      {isLoading && <div className="text-sm text-slate-400">Loading…</div>}
      {data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-3 py-2 font-medium">Pool</th>
                <th className="text-right px-3 py-2 font-medium">Members</th>
                <th className="text-left px-3 py-2 font-medium">Monitors</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((p) => (
                <tr
                  key={p.name}
                  className="border-t border-slate-100 cursor-pointer hover:bg-slate-50"
                  onClick={() => setExpanded(expanded?.name === p.name ? null : p)}
                >
                  <td className="px-3 py-2 font-medium text-slate-800">{p.name}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{p.members.length}</td>
                  <td className="px-3 py-2 text-slate-600">{p.monitor_names.join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {expanded && (
        <Card className="mt-4 p-4">
          <div className="text-sm font-medium text-slate-800 mb-2">{expanded.name} members</div>
          <table className="w-full text-xs">
            <thead className="text-slate-500 uppercase tracking-wide">
              <tr>
                <th className="text-left py-1">Node</th>
                <th className="text-left py-1">IP</th>
                <th className="text-right py-1">Port</th>
              </tr>
            </thead>
            <tbody>
              {expanded.members.map((m) => (
                <tr key={`${m.node_name}:${m.port}`} className="border-t border-slate-100">
                  <td className="py-1.5 break-all">{m.node_name}</td>
                  <td className="py-1.5 font-mono break-all">
                    {nodesByName[m.node_name]?.address ?? "unresolved"}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">{m.port}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
