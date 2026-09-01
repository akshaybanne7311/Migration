import { useMemo, useState } from "react";
import { useNodes, usePools, useValidatedSession, useVips } from "../api/queries";
import type { Vip } from "../api/types";
import { F5GuiPreview } from "../components/F5GuiPreview";
import { VipSummaryTable } from "../components/VipSummaryTable";
import { Card, EmptyState, PageHeader } from "../components/ui";

export function F5GuiPreviewPage() {
  const { sessionId } = useValidatedSession();
  const [search, setSearch] = useState("");
  const { data: vipsData, isLoading } = useVips(sessionId, search);
  const { data: poolsData } = usePools(sessionId);
  const { data: nodesData } = useNodes(sessionId);
  const [openVip, setOpenVip] = useState<Vip | null>(null);

  const poolsByName = useMemo(
    () => Object.fromEntries((poolsData?.items ?? []).map((p) => [p.name, p])),
    [poolsData],
  );
  const nodesByName = useMemo(
    () => Object.fromEntries((nodesData?.items ?? []).map((n) => [n.name, n])),
    [nodesData],
  );

  if (!sessionId) {
    return (
      <div>
        <PageHeader title="F5 GUI Preview" />
        <EmptyState title="No session selected" subtitle="Pick a session from the top bar first." />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="F5 GUI Preview"
        subtitle="See any VIP the way it looks in the BIG-IP Configuration Utility, edit fields, and get the real TMSH command for the change."
      />
      <div className="mb-4">
        <input
          type="text"
          placeholder="Search by VIP name or IP…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full max-w-sm border border-slate-300 rounded-md px-3 py-1.5 text-sm"
        />
      </div>

      {isLoading && <div className="text-sm text-slate-400">Loading…</div>}
      {vipsData && vipsData.items.length === 0 && <EmptyState title="No VIPs match" />}
      {vipsData && vipsData.items.length > 0 && (
        <Card>
          <VipSummaryTable vips={vipsData.items} poolsByName={poolsByName} onRowClick={(v) => setOpenVip(v)} />
        </Card>
      )}

      {openVip && (
        <F5GuiPreview
          vip={openVip}
          pool={openVip.pool_name ? poolsByName[openVip.pool_name] : undefined}
          allVips={vipsData?.items ?? [openVip]}
          nodesByName={nodesByName}
          sessionId={sessionId}
          onClose={() => setOpenVip(null)}
        />
      )}
    </div>
  );
}
