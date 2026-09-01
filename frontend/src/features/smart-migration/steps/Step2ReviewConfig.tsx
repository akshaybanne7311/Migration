import { useMemo, useState } from "react";
import { useNodes, usePools, useValidatedSession, useVips } from "../../../api/queries";
import type { Vip } from "../../../api/types";
import { VipDetailDrawer } from "../../../components/VipDetailDrawer";
import { VipSummaryTable } from "../../../components/VipSummaryTable";
import { Card, EmptyState } from "../../../components/ui";
import { useWizardStore } from "../state/wizardStore";

export function Step2ReviewConfig() {
  const { sessionId } = useValidatedSession();
  const selectedVipNames = useWizardStore((s) => s.selectedVipNames);
  const { data: vipsData } = useVips(sessionId);
  const { data: poolsData, isLoading: poolsLoading } = usePools(sessionId);
  const { data: nodesData } = useNodes(sessionId);
  const [selectedVip, setSelectedVip] = useState<Vip | null>(null);

  const poolsByName = useMemo(
    () => Object.fromEntries((poolsData?.items ?? []).map((p) => [p.name, p])),
    [poolsData],
  );
  const nodesByName = useMemo(
    () => Object.fromEntries((nodesData?.items ?? []).map((n) => [n.name, n])),
    [nodesData],
  );

  const selectedVips = useMemo(
    () => (vipsData?.items ?? []).filter((v) => selectedVipNames.has(v.name)),
    [vipsData, selectedVipNames],
  );

  if (selectedVips.length === 0) {
    return <EmptyState title="No VIPs selected" subtitle="Go back to Step 1 to select VIPs." />;
  }

  return (
    <div>
      <p className="text-sm text-slate-500 mb-4">
        Review the current configuration for the {selectedVips.length} selected VIP
        {selectedVips.length === 1 ? "" : "s"}. Click a row for full detail, including current
        pool members.
      </p>
      <Card>
        <VipSummaryTable
          vips={selectedVips}
          poolsByName={poolsByName}
          onRowClick={(v) => setSelectedVip(v)}
        />
      </Card>

      {selectedVip && (
        <VipDetailDrawer
          vip={selectedVip}
          pool={selectedVip.pool_name ? poolsByName[selectedVip.pool_name] : undefined}
          poolsLoading={poolsLoading}
          nodesByName={nodesByName}
          allVips={selectedVips}
          sessionId={sessionId}
          onClose={() => setSelectedVip(null)}
        />
      )}
    </div>
  );
}
