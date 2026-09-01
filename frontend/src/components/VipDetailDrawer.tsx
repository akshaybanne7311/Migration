import { useState } from "react";
import { createPortal } from "react-dom";
import type { NodeObj, Pool, Vip } from "../api/types";
import { Button } from "./ui";
import { GuiPreview } from "./GuiPreview";

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3 py-1.5 border-b border-slate-100 last:border-0">
      <span className="text-xs text-slate-400 shrink-0">{label}</span>
      <span className="text-sm text-slate-700 text-right break-all">{value ?? "—"}</span>
    </div>
  );
}

export function VipDetailDrawer({
  vip,
  pool,
  poolsLoading = false,
  nodesByName,
  allVips,
  sessionId,
  onClose,
}: {
  vip: Vip;
  pool: Pool | undefined;
  poolsLoading?: boolean;
  nodesByName: Record<string, NodeObj>;
  allVips?: Vip[];
  sessionId?: string | null;
  onClose: () => void;
}) {
  const [showFullConfig, setShowFullConfig] = useState(false);
  const [showGuiPreview, setShowGuiPreview] = useState(false);

  return createPortal(
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-slate-900/20" onClick={onClose} />
      <div className="relative w-full max-w-md bg-white h-full shadow-xl border-l border-slate-200 overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-slate-200 px-5 py-4 flex items-start justify-between">
          <div>
            <div className="text-xs text-slate-400">VIP</div>
            <div className="text-sm font-semibold text-slate-900 break-all">{vip.name}</div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 text-lg leading-none">
            ×
          </button>
        </div>

        <div className="px-5 py-4">
          <Field label="IP" value={vip.destination_address} />
          <Field label="Port" value={vip.destination_port} />
          <Field label="Protocol" value={vip.ip_protocol?.toUpperCase()} />
          <Field label="Pool" value={vip.pool_name} />
          <Field label="Persistence" value={vip.persistence} />
          <Field label="VLANs" value={vip.vlans.length ? vip.vlans.join(", ") : "all (vlans-disabled)"} />
          <Field
            label="Profiles"
            value={vip.profiles.length ? vip.profiles.map((p) => p.name).join(", ") : "—"}
          />
          <Field label="Monitor" value={vip.monitor_names.join(", ")} />
          <Field label="SNAT" value={vip.snat_type} />
          <Field label="iRules" value={vip.irules.length ? vip.irules.join(", ") : "—"} />

          <div className="mt-5">
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

          <div className="mt-5 flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setShowFullConfig(true)}>
              View Full Configuration
            </Button>
            <Button variant="secondary" onClick={() => setShowGuiPreview(true)}>
              Preview in GUI
            </Button>
          </div>
        </div>
      </div>

      {showGuiPreview && (
        <GuiPreview
          vip={vip}
          pool={pool}
          allVips={allVips ?? [vip]}
          nodesByName={nodesByName}
          sessionId={sessionId ?? null}
          onClose={() => setShowGuiPreview(false)}
        />
      )}

      {showFullConfig && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-6"
          onClick={() => setShowFullConfig(false)}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
              <div className="text-sm font-medium">Full parsed configuration</div>
              <button onClick={() => setShowFullConfig(false)} className="text-slate-400 hover:text-slate-700">
                ×
              </button>
            </div>
            <pre className="text-xs p-5 whitespace-pre-wrap break-all font-mono text-slate-700">
              {JSON.stringify(JSON.parse(vip.source_stanza_json || "{}"), null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>,
    document.body,
  );
}
