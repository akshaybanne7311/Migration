import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { useSessionsList, useSessionStore } from "../api/queries";
import { Button, Card, EmptyState, PageHeader } from "../components/ui";
import { toast } from "../components/toastStore";

export function SessionsPage() {
  const { data: sessions, isLoading } = useSessionsList();
  const { currentSessionId, setCurrentSessionId } = useSessionStore();
  const queryClient = useQueryClient();
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);

  async function handleDelete(id: string) {
    const name = sessions?.find((s) => s.id === id)?.name ?? id;
    await api.deleteSession(id);
    queryClient.removeQueries({ queryKey: ["session", id] });
    queryClient.invalidateQueries({ queryKey: ["sessions"] });
    if (currentSessionId === id) {
      setCurrentSessionId(null);
    }
    setPendingDelete(null);
    toast("info", `Session "${name}" deleted.`);
  }

  return (
    <div>
      <PageHeader title="Sessions" subtitle="Each upload becomes an isolated session." />

      {isLoading && <div className="text-sm text-slate-400">Loading…</div>}
      {!isLoading && (!sessions || sessions.length === 0) && (
        <EmptyState title="No sessions yet" subtitle="Upload a UCS file to get started." />
      )}

      {sessions && sessions.length > 0 && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-4 py-2 font-medium">Name</th>
                <th className="text-left px-4 py-2 font-medium">Status</th>
                <th className="text-right px-4 py-2 font-medium">VIPs</th>
                <th className="text-right px-4 py-2 font-medium">Pools</th>
                <th className="text-right px-4 py-2 font-medium">Nodes</th>
                <th className="text-right px-4 py-2 font-medium">VLANs</th>
                <th className="text-left px-4 py-2 font-medium">Created</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr
                  key={s.id}
                  className={`border-t border-slate-100 ${
                    s.id === currentSessionId ? "bg-blue-50/40" : ""
                  }`}
                >
                  <td className="px-4 py-2.5">
                    <div className="font-medium text-slate-800">{s.name}</div>
                    <div className="text-xs text-slate-400">{s.source_filename}</div>
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`text-xs px-2 py-0.5 rounded border ${
                        s.status === "ready"
                          ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                          : s.status === "failed"
                            ? "bg-red-50 text-red-700 border-red-200"
                            : "bg-slate-50 text-slate-600 border-slate-200"
                      }`}
                    >
                      {s.status}
                    </span>
                    {s.error_message && (
                      <div className="text-xs text-red-500 mt-0.5">{s.error_message}</div>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{s.vip_count}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{s.pool_count}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{s.node_count}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{s.vlan_count}</td>
                  <td className="px-4 py-2.5 text-slate-500">
                    {new Date(s.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5 text-right whitespace-nowrap">
                    {s.status === "ready" && s.id !== currentSessionId && (
                      <Button variant="secondary" onClick={() => setCurrentSessionId(s.id)}>
                        Use
                      </Button>
                    )}
                    {s.id === currentSessionId && (
                      <span className="text-xs text-blue-700 font-medium mr-2">Current</span>
                    )}
                    {pendingDelete === s.id ? (
                      <span className="inline-flex items-center gap-2 ml-2">
                        <span className="text-xs text-slate-500">Delete permanently?</span>
                        <Button variant="danger" onClick={() => handleDelete(s.id)}>
                          Confirm
                        </Button>
                        <Button variant="ghost" onClick={() => setPendingDelete(null)}>
                          Cancel
                        </Button>
                      </span>
                    ) : (
                      <Button variant="ghost" onClick={() => setPendingDelete(s.id)}>
                        Delete
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
