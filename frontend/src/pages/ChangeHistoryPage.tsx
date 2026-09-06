import { useMemo, useState } from "react";
import type { ConfigRevision } from "../api/types";
import { useCommandHistory, useConfigRevisions, useValidatedSession } from "../api/queries";
import { Card, EmptyState, PageHeader } from "../components/ui";

function CommandHistoryTab({ sessionId }: { sessionId: string }) {
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

  return (
    <div>
      <div className="mb-4 px-3 py-2 rounded-md text-xs bg-amber-50 border border-amber-200 text-amber-800 max-w-2xl">
        Commands that referenced a password, passphrase, or shared key are marked{" "}
        <span className="font-semibold">SECRET</span> below — the value itself is redacted before it's ever
        stored, so you can see that a credential was changed, by whom, and when, without the credential
        being readable here.
      </div>

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
                    {e.contains_secret && (
                      <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded border bg-red-50 text-red-700 border-red-200 uppercase tracking-wide">
                        secret
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

function DiffLines({ text }: { text: string }) {
  return (
    <pre className="text-[11px] font-mono leading-relaxed overflow-x-auto px-3 py-2 bg-slate-900 rounded-md">
      {text.split("\n").map((line, i) => {
        let color = "text-slate-300";
        if (line.startsWith("+++") || line.startsWith("---") || line.startsWith("@@")) color = "text-sky-400";
        else if (line.startsWith("+")) color = "text-emerald-400";
        else if (line.startsWith("-")) color = "text-red-400";
        return (
          <div key={i} className={color}>
            {line || " "}
          </div>
        );
      })}
    </pre>
  );
}

function ConfigRevisionRow({ revision }: { revision: ConfigRevision }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-t border-slate-100 first:border-t-0">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-slate-50"
      >
        <span className="text-slate-400 text-xs w-4">{open ? "▾" : "▸"}</span>
        <span className="text-slate-500 font-mono text-xs whitespace-nowrap w-44">{revision.timestamp.replace("T", " ").slice(0, 19)}</span>
        <span className="text-slate-700 text-xs font-mono">{revision.config_file}</span>
        <span className="text-slate-400 text-xs">#{revision.patch_number}</span>
        <span className="text-emerald-600 text-xs">+{revision.lines_added}</span>
        <span className="text-red-600 text-xs">-{revision.lines_removed}</span>
        {revision.contains_secret && (
          <span className="text-[10px] px-1.5 py-0.5 rounded border bg-red-50 text-red-700 border-red-200 uppercase tracking-wide">
            secret
          </span>
        )}
      </button>
      {open && (
        <div className="px-3 pb-3">
          <DiffLines text={revision.diff_text} />
        </div>
      )}
    </div>
  );
}

function ConfigRevisionsTab({ sessionId }: { sessionId: string }) {
  const [configFile, setConfigFile] = useState("");
  const { data, isLoading } = useConfigRevisions(sessionId, { configFile: configFile || undefined });

  return (
    <div>
      <div className="mb-4 px-3 py-2 rounded-md text-xs bg-sky-50 border border-sky-200 text-sky-800 max-w-2xl">
        TMOS keeps a real, timestamped unified-diff patch for every save to bigip.conf and related files
        (<code>config/.diffVersions/</code>) — more granular than the command log above, since it shows the
        actual config lines that changed. Same redaction policy applies: any secret value inside a diff line
        is stripped before storage and marked <span className="font-semibold">SECRET</span>.
      </div>

      {data && data.config_files.length > 0 && (
        <div className="mb-4 flex items-center gap-4 flex-wrap">
          <select
            value={configFile}
            onChange={(e) => setConfigFile(e.target.value)}
            className="text-sm border border-slate-300 rounded-md px-2 py-1"
          >
            <option value="">All files ({data.config_files.length})</option>
            {data.config_files.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
          <span className="text-xs text-slate-400">
            {data.total} revision{data.total === 1 ? "" : "s"} shown of {data.total_all} total
          </span>
        </div>
      )}

      {isLoading && <div className="text-sm text-slate-400">Loading…</div>}
      {data && data.items.length === 0 && (
        <EmptyState
          title="No config revision history found"
          subtitle="This archive doesn't have a config/.diffVersions/ directory, or it only contained the internal BigDB.dat database, which is excluded as noise."
        />
      )}

      {data && data.items.length > 0 && (
        <Card className="overflow-hidden">
          {data.items.map((r) => (
            <ConfigRevisionRow key={`${r.config_file}:${r.patch_number}`} revision={r} />
          ))}
        </Card>
      )}
    </div>
  );
}

export function ChangeHistoryPage() {
  const { sessionId, session } = useValidatedSession();
  const [tab, setTab] = useState<"commands" | "diffs">("commands");

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
        subtitle={`Real, timestamped change history recovered from ${session?.name ?? "this session"}'s archive — shell command log and TMOS's own per-save config diffs. This is exactly what a TAC engineer would pull first to answer "what changed, and when."`}
      />

      <div className="mb-4 flex gap-1">
        {(
          [
            ["commands", "Commands (tmsh history)"],
            ["diffs", "Config Diffs (per-save)"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-3 py-1.5 text-xs font-medium rounded-md ${
              tab === key ? "bg-blue-50 text-blue-700" : "text-slate-500 hover:bg-slate-100"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "commands" ? <CommandHistoryTab sessionId={sessionId} /> : <ConfigRevisionsTab sessionId={sessionId} />}
    </div>
  );
}
