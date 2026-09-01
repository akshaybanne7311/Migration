import { useValidatedSession, useVlans } from "../api/queries";
import { Card, EmptyState, PageHeader } from "../components/ui";

export function SystemConfigPage() {
  const { sessionId } = useValidatedSession();
  const { data, isLoading } = useVlans(sessionId);

  if (!sessionId) {
    return (
      <div>
        <PageHeader title="System Config" />
        <EmptyState title="No session selected" />
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="System Config" subtitle="VLAN definitions parsed from this session" />
      {isLoading && <div className="text-sm text-slate-400">Loading…</div>}
      {data && data.items.length === 0 && <EmptyState title="No VLAN objects parsed" />}
      {data && data.items.length > 0 && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-3 py-2 font-medium">VLAN</th>
                <th className="text-right px-3 py-2 font-medium">Tag</th>
                <th className="text-left px-3 py-2 font-medium">Interfaces</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((v) => (
                <tr key={v.name} className="border-t border-slate-100">
                  <td className="px-3 py-2 font-medium text-slate-800">{v.name}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{v.tag ?? "—"}</td>
                  <td className="px-3 py-2 text-slate-600">{v.interfaces.join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
