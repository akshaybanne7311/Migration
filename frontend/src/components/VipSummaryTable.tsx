import type { Pool, Vip } from "../api/types";
import { Checkbox } from "./ui";

function formatDestination(vip: Vip): string {
  const addr = vip.address_family === "ipv6" ? vip.destination_address : vip.destination_address;
  return `${addr}:${vip.destination_port}`;
}

export function VipSummaryTable({
  vips,
  poolsByName,
  selectable = false,
  selected,
  onToggle,
  onSelectAll,
  onRowClick,
  actionLabel,
}: {
  vips: Vip[];
  poolsByName: Record<string, Pool>;
  selectable?: boolean;
  selected?: Set<string>;
  onToggle?: (vipName: string) => void;
  onSelectAll?: (checked: boolean) => void;
  onRowClick?: (vip: Vip) => void;
  actionLabel?: (vip: Vip) => string;
}) {
  const allSelected = selectable && vips.length > 0 && vips.every((v) => selected?.has(v.name));

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
          <tr>
            {selectable && (
              <th className="px-3 py-2 w-8">
                <Checkbox checked={allSelected} onChange={(v) => onSelectAll?.(v)} label="" />
              </th>
            )}
            <th className="text-left px-3 py-2 font-medium">VIP</th>
            <th className="text-left px-3 py-2 font-medium">IP:Port</th>
            <th className="text-left px-3 py-2 font-medium">Pool</th>
            <th className="text-right px-3 py-2 font-medium">Members</th>
            <th className="text-right px-3 py-2 font-medium">VLANs</th>
            <th className="text-right px-3 py-2 font-medium">Profiles</th>
            {actionLabel && <th className="text-right px-3 py-2 font-medium">Action</th>}
          </tr>
        </thead>
        <tbody>
          {vips.map((vip) => {
            const pool = vip.pool_name ? poolsByName[vip.pool_name] : undefined;
            const memberCount = pool?.members.length ?? 0;
            return (
              <tr
                key={vip.name}
                className={`border-t border-slate-100 ${onRowClick ? "cursor-pointer hover:bg-slate-50" : ""}`}
                onClick={() => onRowClick?.(vip)}
              >
                {selectable && (
                  <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                    <Checkbox
                      checked={!!selected?.has(vip.name)}
                      onChange={() => onToggle?.(vip.name)}
                      label=""
                    />
                  </td>
                )}
                <td className="px-3 py-2 font-medium text-slate-800">{vip.name}</td>
                <td className="px-3 py-2 text-slate-600 font-mono text-xs">
                  {formatDestination(vip)}
                </td>
                <td className="px-3 py-2 text-slate-600">{vip.pool_name ?? "—"}</td>
                <td className="px-3 py-2 text-right tabular-nums">{memberCount}</td>
                <td className="px-3 py-2 text-right tabular-nums">{vip.vlans.length}</td>
                <td className="px-3 py-2 text-right tabular-nums">{vip.profiles.length}</td>
                {actionLabel && (
                  <td className="px-3 py-2 text-right text-xs text-slate-400">
                    {actionLabel(vip)}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
