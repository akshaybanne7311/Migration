import type { NodeObj, Pool, Vip } from "../../../api/types";
import { Card } from "../../../components/ui";

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3 py-1 text-xs">
      <span className="text-slate-400 shrink-0">{label}</span>
      <span className="text-slate-700 text-right break-all">{value ?? "—"}</span>
    </div>
  );
}

export function VipReviewCard({
  vip,
  pool,
  poolsLoading,
  nodesByName,
  defaultOpen,
}: {
  vip: Vip;
  pool: Pool | undefined;
  poolsLoading: boolean;
  nodesByName: Record<string, NodeObj>;
  defaultOpen: boolean;
}) {
  return (
    <Card className="overflow-hidden">
      <details open={defaultOpen}>
        <summary className="cursor-pointer list-none px-4 py-3 flex items-center justify-between gap-3 hover:bg-slate-50">
          <div className="min-w-0">
            <div className="text-sm font-medium text-slate-800 truncate">{vip.name}</div>
            <div className="text-xs text-slate-400 font-mono">
              {vip.destination_address}:{vip.destination_port}
            </div>
          </div>
          <div className="text-xs text-slate-500 shrink-0">{vip.pool_name ?? "no pool"}</div>
        </summary>

        <div className="px-4 pb-4 border-t border-slate-100 pt-3">
          <Field label="Protocol" value={vip.ip_protocol?.toUpperCase()} />
          <Field label="Persistence" value={vip.persistence} />
          <Field label="Monitor" value={vip.monitor_names.join(", ")} />
          <Field
            label="VLANs"
            value={vip.vlans.length ? vip.vlans.join(", ") : "all (vlans-disabled)"}
          />
          <Field
            label="Profiles"
            value={vip.profiles.length ? vip.profiles.map((p) => p.name).join(", ") : "—"}
          />

          <div className="mt-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">
              Current Pool Members
            </div>
            {pool && pool.members.length > 0 ? (
              <table className="w-full text-xs border border-slate-200 rounded-md overflow-hidden">
                <thead className="bg-slate-50 text-slate-500">
                  <tr>
                    <th className="text-left px-2 py-1.5 font-medium">Node</th>
                    <th className="text-left px-2 py-1.5 font-medium">IP</th>
                    <th className="text-right px-2 py-1.5 font-medium">Port</th>
                    <th className="text-left px-2 py-1.5 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {pool.members.map((m) => (
                    <tr key={`${m.node_name}:${m.port}`} className="border-t border-slate-100">
                      <td className="px-2 py-1.5 break-all">{m.node_name}</td>
                      <td className="px-2 py-1.5 font-mono break-all">
                        {nodesByName[m.node_name]?.address ?? "unresolved"}
                      </td>
                      <td className="px-2 py-1.5 text-right tabular-nums">{m.port}</td>
                      <td className="px-2 py-1.5 text-slate-500">{m.session_state ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="text-xs text-slate-400 italic">
                {!vip.pool_name
                  ? "No pool assigned."
                  : poolsLoading
                    ? "Loading pool members…"
                    : "No members parsed for this pool."}
              </div>
            )}
          </div>
        </div>
      </details>
    </Card>
  );
}
