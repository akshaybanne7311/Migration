import { useNodes, useValidatedSession } from "../api/queries";
import { Card, EmptyState, PageHeader } from "../components/ui";

export function NodesPage() {
  const { sessionId } = useValidatedSession();
  const { data, isLoading } = useNodes(sessionId);

  if (!sessionId) {
    return (
      <div>
        <PageHeader title="Nodes" />
        <EmptyState title="No session selected" />
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Nodes" subtitle={`${data?.total ?? 0} nodes`} />
      {isLoading && <div className="text-sm text-slate-400">Loading…</div>}
      {data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-3 py-2 font-medium">Node</th>
                <th className="text-left px-3 py-2 font-medium">Address</th>
                <th className="text-left px-3 py-2 font-medium">Family</th>
                <th className="text-right px-3 py-2 font-medium">Pools</th>
                <th className="text-right px-3 py-2 font-medium">VIPs</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((n) => (
                <tr key={n.name} className="border-t border-slate-100">
                  <td className="px-3 py-2 font-medium text-slate-800 break-all">{n.name}</td>
                  <td className="px-3 py-2 font-mono text-xs break-all">{n.address}</td>
                  <td className="px-3 py-2 text-slate-500 uppercase text-xs">{n.address_family}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {n.pool_count}
                    {(n.pool_count ?? 0) > 1 && (
                      <span className="ml-1 text-[10px] text-blue-600 font-medium">shared</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{n.vip_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
