import { useMemo, useState } from "react";
import { useNodes, usePools, useValidatedSession, useVips } from "../../../api/queries";
import type { Vip } from "../../../api/types";
import { VipDetailDrawer } from "../../../components/VipDetailDrawer";
import { EmptyState } from "../../../components/ui";
import { useWizardStore } from "../state/wizardStore";
import { VipReviewCard } from "../components/VipReviewCard";

const AUTO_EXPAND_THRESHOLD = 3;

export function Step2ReviewConfig() {
  const { sessionId } = useValidatedSession();
  const selectedVipNames = useWizardStore((s) => s.selectedVipNames);
  const { data: vipsData } = useVips(sessionId);
  const { data: poolsData, isLoading: poolsLoading } = usePools(sessionId);
  const { data: nodesData } = useNodes(sessionId);
  const [fullConfigVip, setFullConfigVip] = useState<Vip | null>(null);

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

  const autoExpand = selectedVips.length <= AUTO_EXPAND_THRESHOLD;

  return (
    <div>
      <p className="text-sm text-slate-500 mb-4">
        Current configuration for the {selectedVips.length} selected VIP
        {selectedVips.length === 1 ? "" : "s"} — pool members, VLANs, and profiles shown here are
        what exists today, before any change is applied.
        {!autoExpand && " Click a card to expand its detail."}
      </p>
      <div className="space-y-2">
        {selectedVips.map((vip) => (
          <div key={vip.name}>
            <VipReviewCard
              vip={vip}
              pool={vip.pool_name ? poolsByName[vip.pool_name] : undefined}
              poolsLoading={poolsLoading}
              nodesByName={nodesByName}
              defaultOpen={autoExpand}
            />
            <button
              onClick={() => setFullConfigVip(vip)}
              className="text-xs text-blue-700 hover:underline mt-1 ml-1"
            >
              View full parsed configuration →
            </button>
          </div>
        ))}
      </div>

      {fullConfigVip && (
        <VipDetailDrawer
          vip={fullConfigVip}
          pool={fullConfigVip.pool_name ? poolsByName[fullConfigVip.pool_name] : undefined}
          poolsLoading={poolsLoading}
          nodesByName={nodesByName}
          allVips={selectedVips}
          sessionId={sessionId}
          onClose={() => setFullConfigVip(null)}
        />
      )}
    </div>
  );
}
