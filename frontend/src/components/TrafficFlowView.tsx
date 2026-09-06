import type { TrafficFlowResult } from "../api/types";
import { Card } from "./ui";

const MEMBER_COLORS = ["#0284c7", "#16a34a", "#9333ea", "#d97706", "#0d9488", "#dc2626", "#4f46e5", "#65a30d"];

function short(name: string): string {
  return name.replace("/Common/", "");
}

export function TrafficFlowView({ flow }: { flow: TrafficFlowResult }) {
  const colorByMember = new Map<string, string>();
  flow.members.forEach((m, i) => colorByMember.set(m.name, MEMBER_COLORS[i % MEMBER_COLORS.length]));

  return (
    <div>
      <div className="mb-4 px-3 py-2 rounded-md text-xs bg-sky-50 border border-sky-200 text-sky-800 max-w-3xl">
        No real packet capture exists in this session's archive (verified against all real UCS/QKView uploads) — this
        simulates a connection's decision path through the real parsed config instead: real pool members, real
        load-balancing method, real persistence/SNAT settings. It is not a replay of real traffic.
      </div>

      <Card className="p-4 mb-4">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          <div>
            <div className="text-xs text-slate-400 uppercase tracking-wide">Destination</div>
            <div className="font-mono text-slate-800">{flow.destination}</div>
          </div>
          <div>
            <div className="text-xs text-slate-400 uppercase tracking-wide">Protocol</div>
            <div className="text-slate-800">{flow.protocol}</div>
          </div>
          <div>
            <div className="text-xs text-slate-400 uppercase tracking-wide">Pool</div>
            <div className="text-slate-800">{flow.pool_name ? short(flow.pool_name) : "None"}</div>
          </div>
          <div>
            <div className="text-xs text-slate-400 uppercase tracking-wide">LB Method</div>
            <div className="text-slate-800">{flow.load_balancing_method}</div>
          </div>
          <div>
            <div className="text-xs text-slate-400 uppercase tracking-wide">Persistence</div>
            <div className="text-slate-800">{flow.persistence ? short(flow.persistence) : "None"}</div>
          </div>
          <div>
            <div className="text-xs text-slate-400 uppercase tracking-wide">SNAT</div>
            <div className="text-slate-800">{flow.snat_type ?? "None"}</div>
          </div>
          <div className="col-span-2">
            <div className="text-xs text-slate-400 uppercase tracking-wide">Monitors</div>
            <div className="text-slate-800">{flow.monitors.length ? flow.monitors.map(short).join(", ") : "None"}</div>
          </div>
        </div>
      </Card>

      <div
        className={`mb-4 px-3 py-2 rounded-md text-xs max-w-3xl ${
          flow.load_balancing_is_simulated_as_round_robin
            ? "bg-amber-50 border border-amber-200 text-amber-800"
            : "bg-emerald-50 border border-emerald-200 text-emerald-800"
        }`}
      >
        {flow.note}
      </div>

      <Card className="overflow-hidden mb-4">
        <div className="px-3 py-2 text-sm font-medium text-slate-800 border-b border-slate-100">
          Pool Members ({flow.members.length})
        </div>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
            <tr>
              <th className="text-left px-3 py-2 font-medium w-4"></th>
              <th className="text-left px-3 py-2 font-medium">Member</th>
              <th className="text-left px-3 py-2 font-medium">Address</th>
              <th className="text-left px-3 py-2 font-medium">Port</th>
              <th className="text-left px-3 py-2 font-medium">State</th>
            </tr>
          </thead>
          <tbody>
            {flow.members.map((m) => (
              <tr key={m.name} className="border-t border-slate-100">
                <td className="px-3 py-2">
                  <span
                    className="inline-block w-2.5 h-2.5 rounded-full"
                    style={{ background: m.enabled ? colorByMember.get(m.name) : "#cbd5e1" }}
                  />
                </td>
                <td className="px-3 py-2 text-slate-700">{short(m.name)}</td>
                <td className="px-3 py-2 font-mono text-slate-600">{m.address}</td>
                <td className="px-3 py-2 font-mono text-slate-600">{m.port}</td>
                <td className="px-3 py-2">
                  {m.enabled ? (
                    <span className="text-emerald-600">Enabled</span>
                  ) : (
                    <span className="text-slate-400">Disabled</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {flow.simulated_requests.length > 0 && (
        <Card className="p-4">
          <div className="text-sm font-medium text-slate-800 mb-3">
            Simulated Requests ({flow.simulated_requests.length})
          </div>
          <div className="flex flex-wrap gap-2">
            {flow.simulated_requests.map((r) => (
              <div
                key={r.sequence}
                className="flex flex-col items-center gap-1 px-2.5 py-2 rounded-md border border-slate-200 text-xs"
                title={`Request ${r.sequence} -> ${r.member_name} (${r.member_address})`}
              >
                <span className="text-slate-400">#{r.sequence}</span>
                <span
                  className="inline-block w-2.5 h-2.5 rounded-full"
                  style={{ background: colorByMember.get(r.member_name) }}
                />
                <span className="font-mono text-slate-600">{r.member_address}</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
