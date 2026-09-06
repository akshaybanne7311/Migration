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
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [pendingBulkDelete, setPendingBulkDelete] = useState(false);

  async function deleteOne(id: string) {
    await api.deleteSession(id);
    queryClient.removeQueries({ queryKey: ["session", id] });
    if (currentSessionId === id) {
      setCurrentSessionId(null);
    }
  }

  async function handleDelete(id: string) {
    const name = sessions?.find((s) => s.id === id)?.name ?? id;
    await deleteOne(id);
    queryClient.invalidateQueries({ queryKey: ["sessions"] });
    setPendingDelete(null);
    toast("info", `Session "${name}" deleted.`);
  }

  const failedSessions = sessions?.filter((s) => s.status === "failed") ?? [];

  async function handleClearFailed() {
    for (const s of failedSessions) {
      await deleteOne(s.id);
    }
    queryClient.invalidateQueries({ queryKey: ["sessions"] });
    toast("info", `Cleared ${failedSessions.length} failed session(s).`);
  }

  function toggleOne(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    if (!sessions) return;
    setSelected((prev) => (prev.size === sessions.length ? new Set() : new Set(sessions.map((s) => s.id))));
  }

  async function handleBulkDelete() {
    const ids = Array.from(selected);
    setBulkDeleting(true);
    try {
      for (const id of ids) {
        await deleteOne(id);
      }
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      toast("info", `Deleted ${ids.length} session${ids.length === 1 ? "" : "s"}.`);
      setSelected(new Set());
    } finally {
      setBulkDeleting(false);
      setPendingBulkDelete(false);
    }
  }

  return (
    <div>
      <PageHeader title="Sessions" subtitle="Each upload becomes an isolated session." />

      {failedSessions.length > 0 && (
        <div className="mb-3 flex items-center justify-between rounded-md border border-red-200 bg-red-50 px-4 py-2">
          <span className="text-sm text-red-700">
            {failedSessions.length} failed session{failedSessions.length === 1 ? "" : "s"} in this list.
          </span>
          <Button variant="danger" onClick={handleClearFailed}>
            Clear failed
          </Button>
        </div>
      )}

      {selected.size > 0 && (
        <div className="mb-3 flex items-center justify-between rounded-md border border-slate-200 bg-slate-50 px-4 py-2">
          <span className="text-sm text-slate-700">
            {selected.size} session{selected.size === 1 ? "" : "s"} selected
          </span>
          {pendingBulkDelete ? (
            <span className="inline-flex items-center gap-2">
              <span className="text-xs text-slate-500">Delete {selected.size} permanently?</span>
              <Button variant="danger" onClick={handleBulkDelete} disabled={bulkDeleting}>
                {bulkDeleting ? "Deleting…" : "Confirm"}
              </Button>
              <Button variant="ghost" onClick={() => setPendingBulkDelete(false)} disabled={bulkDeleting}>
                Cancel
              </Button>
            </span>
          ) : (
            <div className="flex items-center gap-2">
              <Button variant="ghost" onClick={() => setSelected(new Set())}>
                Clear selection
              </Button>
              <Button variant="danger" onClick={() => setPendingBulkDelete(true)}>
                Delete selected
              </Button>
            </div>
          )}
        </div>
      )}

      {isLoading && <div className="text-sm text-slate-400">Loading…</div>}
      {!isLoading && (!sessions || sessions.length === 0) && (
        <EmptyState title="No sessions yet" subtitle="Upload a UCS file to get started." />
      )}

      {sessions && sessions.length > 0 && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
              <tr>
                <th className="px-4 py-2 w-8">
                  <input
                    type="checkbox"
                    checked={sessions.length > 0 && selected.size === sessions.length}
                    ref={(el) => {
                      if (el) el.indeterminate = selected.size > 0 && selected.size < sessions.length;
                    }}
                    onChange={toggleAll}
                    aria-label="Select all sessions"
                  />
                </th>
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
                    <input
                      type="checkbox"
                      checked={selected.has(s.id)}
                      onChange={() => toggleOne(s.id)}
                      aria-label={`Select ${s.name}`}
                    />
                  </td>
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
