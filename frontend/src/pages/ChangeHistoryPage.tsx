import { useMemo, useState } from "react";
import { useCommandHistory, useValidatedSession } from "../api/queries";
import { Card, EmptyState, PageHeader } from "../components/ui";

export function ChangeHistoryPage() {
  const { sessionId, session } = useValidatedSession();
  const [mutatingOnly, setMutatingOnly] = useState(true);
  const [userFilter, setUserFilter] = useState("");
  const { data, isLoading } = useCommandHistory(sessionId, { mutatingOnly });

  const users = useMemo(() => {
    const set = new Set((data?.items ?? []).map((e) => e.user));
    return Array.from(set).sort();
  }, [data]);

  const filtered = useMemo(() => {
    const items = data?.items ?? [];
    return userFilter ? items.filter((e) => e.user === userFilter) : items;
  }, [data, userFilter]);

  if (!sessionId) {
    return (
      <div>
        <PageHeader title="Change History" />
        <EmptyState title="No session selected" subtitle="Pick a session from the top bar first." />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Change History"
        subtitle={`Real, timestamped tmsh commands from ${session?.name ?? "this session"}'s .tmsh-history files inside the archive — shell history, not device config. This is exactly what a TAC engineer would pull first to answer "what changed, and when."`}
      />

      <div className="mb-4 flex items-center gap-4 flex-wrap">
        <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer">
          <input type="checkbox" checked={mutatingOnly} onChange={(e) => setMutatingOnly(e.target.checked)} />
          Config-changing commands only (hide routine show/list monitoring noise)
        </label>
        {users.length > 1 && (
          <select
            value={userFilter}
            onChange={(e) => setUserFilter(e.target.value)}
            className="text-sm border border-slate-300 rounded-md px-2 py-1"
          >
            <option value="">All users ({users.length})</option>
            {users.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>
        )}
        {data && (
          <span className="text-xs text-slate-400">
            {filtered.length} shown{mutatingOnly ? ` of ${data.total_all} total commands` : ""}
          </span>
        )}
      </div>

      {isLoading && <div className="text-sm text-slate-400">Loading…</div>}
      {data && filtered.length === 0 && (
        <EmptyState
          title="No command history found"
          subtitle="Either no .tmsh-history files were in the archive, or none matched the current filter."
        />
      )}

      {filtered.length > 0 && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-3 py-2 font-medium w-40">Timestamp</th>
                <th className="text-left px-3 py-2 font-medium w-40">User</th>
                <th className="text-left px-3 py-2 font-medium">Command</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((e, i) => (
                <tr key={i} className="border-t border-slate-100">
                  <td className="px-3 py-2 text-slate-500 font-mono text-xs whitespace-nowrap">{e.timestamp}</td>
                  <td className="px-3 py-2 text-slate-600">{e.user}</td>
                  <td className="px-3 py-2 font-mono text-xs break-all">
                    {e.command}
                    {e.is_mutating && (
                      <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded border bg-amber-50 text-amber-700 border-amber-200 uppercase tracking-wide">
                        change
                      </span>
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
