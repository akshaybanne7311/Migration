import { useMemo, useState } from "react";
import { useNodes, usePools, useValidatedSession, useVips } from "../api/queries";
import type { Vip } from "../api/types";
import { VipDetailDrawer } from "../components/VipDetailDrawer";
import { VipSummaryTable } from "../components/VipSummaryTable";
import { Button, Card, EmptyState, PageHeader } from "../components/ui";
import { toast } from "../components/toastStore";
import { exportMigrationPlanToExcel } from "../utils/excelExport";

export function VipsPage() {
  const { sessionId, session } = useValidatedSession();
  const [search, setSearch] = useState("");
  const { data: vipsData, isLoading } = useVips(sessionId, search);
  const { data: poolsData, isLoading: poolsLoading } = usePools(sessionId);
  const { data: nodesData } = useNodes(sessionId);
  const [selectedVip, setSelectedVip] = useState<Vip | null>(null);
  const [exporting, setExporting] = useState(false);

  async function handleExportAll() {
    if (!vipsData?.items?.length) return;
    setExporting(true);
    try {
      await exportMigrationPlanToExcel({
        sessionName: session?.name ?? "session",
        selectedVips: vipsData.items,
        kpis: undefined,
        validation: null,
        generated: null,
        outputMode: "changes_only",
      });
      toast("success", `Exported ${vipsData.items.length} VIPs to Excel.`);
    } catch (e) {
      toast("error", e instanceof Error ? e.message : "Excel export failed");
    } finally {
      setExporting(false);
    }
  }

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
        <PageHeader title="VIPs" />
        <EmptyState title="No session selected" />
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="VIPs" subtitle={`${vipsData?.total ?? 0} virtual servers`} />
      <div className="mb-4 flex items-center justify-between gap-3 flex-wrap">
        <input
          type="text"
          placeholder="Search by VIP name or IP…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full max-w-sm border border-slate-300 rounded-md px-3 py-1.5 text-sm"
        />
        <Button
          variant="secondary"
          onClick={handleExportAll}
          disabled={exporting || !vipsData?.items?.length}
        >
          {exporting ? "Exporting…" : "Export all to Excel"}
        </Button>
      </div>

      {isLoading && <div className="text-sm text-slate-400">Loading…</div>}
      {vipsData && vipsData.items.length === 0 && <EmptyState title="No VIPs match" />}
      {vipsData && vipsData.items.length > 0 && (
        <Card>
          <VipSummaryTable
            vips={vipsData.items}
            poolsByName={poolsByName}
            onRowClick={(v) => setSelectedVip(v)}
          />
        </Card>
      )}

      {selectedVip && (
        <VipDetailDrawer
          vip={selectedVip}
          pool={selectedVip.pool_name ? poolsByName[selectedVip.pool_name] : undefined}
          poolsLoading={poolsLoading}
          nodesByName={nodesByName}
          allVips={vipsData?.items}
          sessionId={sessionId}
          onClose={() => setSelectedVip(null)}
        />
      )}
    </div>
  );
}
