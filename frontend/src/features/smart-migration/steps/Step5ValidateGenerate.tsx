import { useState } from "react";
import { api } from "../../../api/client";
import { useSelectionKpis, useValidatedSession, useVips } from "../../../api/queries";
import type { GenerateResult, MigrationPlan, ValidationResult } from "../../../api/types";
import { Button, Card, KpiCard, SeverityBadge } from "../../../components/ui";
import { toast } from "../../../components/toastStore";
import { exportMigrationPlanToExcel } from "../../../utils/excelExport";
import { exportSopDocument } from "../../../utils/sopExport";
import { useWizardStore } from "../state/wizardStore";

function buildPlan(sessionId: string, store: ReturnType<typeof useWizardStore.getState>): MigrationPlan {
  return {
    session_id: sessionId,
    selected_vips: Array.from(store.selectedVipNames),
    common_changes: Array.from(store.chosenChangeTypes)
      .map((ct) => store.commonChanges[ct])
      .filter((c): c is NonNullable<typeof c> => !!c),
    node_changes: store.nodeChanges,
    pool_member_edits: store.poolMemberEdits,
    exceptions: store.exceptions,
    create_network_objects: store.createNetworkObjects,
    output_mode: store.outputMode,
  };
}

function ValidationChecklist({ result }: { result: ValidationResult }) {
  return (
    <Card className="p-4 mb-4">
      <div className="text-sm font-medium text-slate-800 mb-2">Validation</div>
      <div className="space-y-1.5">
        {result.checks.map((c) => (
          <div key={c.id} className="flex items-start justify-between gap-3 text-sm py-1 border-b border-slate-50 last:border-0">
            <div>
              <div className="text-slate-700">{c.label}</div>
              <div className="text-xs text-slate-400">{c.details}</div>
              {c.affected.length > 0 && (
                <ul className="text-xs text-slate-400 list-disc list-inside mt-0.5">
                  {c.affected.slice(0, 5).map((a) => (
                    <li key={a}>{a}</li>
                  ))}
                </ul>
              )}
            </div>
            <SeverityBadge severity={c.severity} />
          </div>
        ))}
      </div>
      <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between">
        <span className="text-sm font-medium">Status</span>
        <span
          className={`text-sm font-semibold ${result.overall === "READY" ? "text-emerald-600" : "text-red-600"}`}
        >
          {result.overall}
        </span>
      </div>
    </Card>
  );
}

function GeneratedOutput({ result }: { result: GenerateResult }) {
  const [tab, setTab] = useState<"tmsh" | "rest" | "as3">("tmsh");

  const text =
    tab === "tmsh"
      ? result.tmsh
      : tab === "rest"
        ? JSON.stringify(result.rest, null, 2)
        : JSON.stringify(result.as3, null, 2);

  function copy() {
    navigator.clipboard.writeText(text);
  }

  function download() {
    const ext = tab === "tmsh" ? "txt" : "json";
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `migration-${tab}.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Card className="p-0 overflow-hidden">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-2">
        <div className="flex gap-1">
          {(["tmsh", "rest", "as3"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md ${
                tab === t ? "bg-blue-50 text-blue-700" : "text-slate-500 hover:bg-slate-100"
              }`}
            >
              {t.toUpperCase()}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={copy}>
            Copy
          </Button>
          <Button variant="secondary" onClick={download}>
            Download
          </Button>
        </div>
      </div>
      {tab === "as3" && result.as3["x-tmos-notes"]?.length > 0 && (
        <div className="px-4 py-2 bg-amber-50 border-b border-amber-100 text-xs text-amber-800">
          AS3 is a transformation view — {result.as3["x-tmos-notes"].length} field(s) don't map
          1:1 from TMOS. See notes below the declaration.
        </div>
      )}
      <div
        className="relative overflow-hidden"
        style={{ background: "#03050a", borderTop: "1px solid var(--border-faint)" }}
      >
        <div className="flex items-center gap-1.5 px-4 py-2" style={{ borderBottom: "1px solid var(--border-faint)" }}>
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: "#ff5c5c" }} />
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: "#ffbd2e" }} />
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: "#27c93f" }} />
          <span className="ml-2 text-[11px] font-mono-neon" style={{ color: "var(--text-dim)" }}>
            migration-output.{tab === "tmsh" ? "txt" : "json"}
          </span>
        </div>
        <pre
          className="font-mono-neon text-[13px] leading-relaxed p-4 overflow-auto max-h-[420px] whitespace-pre-wrap break-all"
          style={{ color: "var(--success-strong)", textShadow: "0 0 8px rgba(43,255,176,0.25)" }}
        >
          {text ||
            "// No output for this selection. In \"Apply changes\" mode that means no change types were chosen in Step 3 — switch to \"Full recreate\" above, or go back and check a change type."}
        </pre>
      </div>
    </Card>
  );
}

export function Step5ValidateGenerate() {
  const { sessionId, session } = useValidatedSession();
  const selectedVipNames = useWizardStore((s) => s.selectedVipNames);
  const chosenChangeTypes = useWizardStore((s) => s.chosenChangeTypes);
  const exceptions = useWizardStore((s) => s.exceptions);
  const nodeChanges = useWizardStore((s) => s.nodeChanges);
  const poolMemberEdits = useWizardStore((s) => s.poolMemberEdits);
  const hasAnyChange =
    chosenChangeTypes.size > 0 ||
    exceptions.length > 0 ||
    nodeChanges.length > 0 ||
    poolMemberEdits.length > 0;
  const { data: kpis } = useSelectionKpis(sessionId, Array.from(selectedVipNames));
  const { data: vipsData } = useVips(sessionId);
  const planId = useWizardStore((s) => s.planId);
  const setPlanId = useWizardStore((s) => s.setPlanId);
  const outputMode = useWizardStore((s) => s.outputMode);
  const setOutputMode = useWizardStore((s) => s.setOutputMode);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [generated, setGenerated] = useState<GenerateResult | null>(null);
  const [exporting, setExporting] = useState<"excel" | "sop" | null>(null);

  const selectedVips = (vipsData?.items ?? []).filter((v) => selectedVipNames.has(v.name));

  async function handleExportExcel() {
    setExporting("excel");
    try {
      await exportMigrationPlanToExcel({
        sessionName: session?.name ?? "migration",
        selectedVips,
        kpis,
        validation,
        generated,
        outputMode,
      });
      toast("success", "Excel workbook downloaded.");
    } catch (e) {
      toast("error", e instanceof Error ? e.message : "Excel export failed");
    } finally {
      setExporting(null);
    }
  }

  async function handleExportSop() {
    setExporting("sop");
    try {
      await exportSopDocument({
        sessionName: session?.name ?? "migration",
        selectedVips,
        kpis,
        validation,
        generated,
        outputMode,
      });
      toast("success", "SOP document downloaded.");
    } catch (e) {
      toast("error", e instanceof Error ? e.message : "SOP export failed");
    } finally {
      setExporting(null);
    }
  }

  async function handleValidate() {
    if (!sessionId) return;
    setBusy(true);
    setError(null);
    setGenerated(null);
    try {
      const plan = buildPlan(sessionId, useWizardStore.getState());
      let currentPlanId = planId;
      if (currentPlanId) {
        await api.updatePlan(sessionId, currentPlanId, plan, 5);
      } else {
        const created = await api.createPlan(sessionId, plan);
        currentPlanId = created.id;
        setPlanId(created.id);
      }
      const result = await api.validatePlan(sessionId, currentPlanId);
      setValidation(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Validation failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleGenerate() {
    if (!sessionId || !planId) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.generatePlan(sessionId, planId);
      setGenerated(result);
      setValidation(result.validation);
      toast(
        "success",
        result.tmsh.trim()
          ? `Generated TMSH/REST/AS3 for ${selectedVipNames.size} VIP${selectedVipNames.size === 1 ? "" : "s"}.`
          : "Generate finished, but produced no output for this selection — see the note in the output panel.",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="mb-5">
        <div className="text-sm font-medium text-slate-800 mb-2">Selection</div>
        <div className="flex flex-wrap gap-3">
          <KpiCard label="VIPs selected" value={kpis?.vips ?? 0} />
          <KpiCard label="Pools" value={kpis?.pools ?? 0} />
          <KpiCard label="Pool Members" value={kpis?.pool_members ?? 0} />
          <KpiCard label="Nodes" value={kpis?.nodes ?? 0} />
          <KpiCard label="VLAN references" value={kpis?.vlan_refs ?? 0} />
        </div>
      </div>

      {validation?.summary && (
        <div className="mb-5">
          <div className="text-sm font-medium text-slate-800 mb-2">
            Migration Summary <span className="text-xs font-normal text-slate-400">— what will actually change</span>
          </div>
          <div className="flex flex-wrap gap-3">
            <KpiCard
              label="VIPs changed / unchanged"
              value={`${validation.summary.vips_changed} / ${validation.summary.vips_unchanged}`}
            />
            <KpiCard label="Pools affected" value={validation.summary.pools_affected} />
            <KpiCard label="Nodes affected" value={validation.summary.nodes_affected} />
            <KpiCard label="VLAN bindings changed" value={validation.summary.vlan_bindings_changed} />
            <KpiCard label="Pool member edits" value={validation.summary.pool_member_edits} />
            <KpiCard label="Objects to create" value={validation.summary.objects_created} />
            <KpiCard label="Objects to modify" value={validation.summary.objects_modified} />
            <KpiCard label="Objects to remove" value={validation.summary.objects_removed} />
            <KpiCard label="Warnings" value={validation.summary.warnings} />
            <KpiCard label="Errors" value={validation.summary.errors} />
          </div>
        </div>
      )}

      <div className="mb-5">
        <div className="text-sm font-medium text-slate-800 mb-2">Output mode</div>
        <div className="flex flex-col gap-2 max-w-xl">
          <label className="flex items-start gap-2 cursor-pointer">
            <input
              type="radio"
              name="output-mode"
              className="mt-1"
              checked={outputMode === "changes_only"}
              onChange={() => setOutputMode("changes_only")}
            />
            <span className="text-sm text-slate-700">
              <span className="font-medium">Apply changes to existing objects</span>
              <span className="block text-xs text-slate-400">
                Target device already has these VIPs, pools, and nodes. Only emits commands for
                fields you actually changed in Steps 3–4.
              </span>
            </span>
          </label>
          <label className="flex items-start gap-2 cursor-pointer">
            <input
              type="radio"
              name="output-mode"
              className="mt-1"
              checked={outputMode === "full_recreate"}
              onChange={() => setOutputMode("full_recreate")}
            />
            <span className="text-sm text-slate-700">
              <span className="font-medium">Full recreate for a new device</span>
              <span className="block text-xs text-slate-400">
                Target device doesn't have these objects yet. Generates complete create commands
                for every selected VIP's monitors, nodes, pool, and virtual — any changes you
                chose are still applied to the recreated values.
              </span>
            </span>
          </label>
        </div>
      </div>

      {outputMode === "changes_only" && selectedVipNames.size > 0 && !hasAnyChange && (
        <div className="mb-4 px-4 py-2.5 rounded-md text-xs bg-amber-50 border border-amber-200 text-amber-700 max-w-xl">
          No changes are configured yet, so "Apply changes" mode has nothing to emit and Generate
          will produce an empty script. Choose a change type in Step 3, add an exception or CSV
          import in Step 4, or switch to "Full recreate for a new device" above if you just want
          these VIPs stood up as-is.
        </div>
      )}

      <div className="flex flex-wrap gap-3 mb-5">
        <Button onClick={handleValidate} disabled={busy || selectedVipNames.size === 0}>
          {busy ? "Working…" : "Validate"}
        </Button>
        <Button
          onClick={handleGenerate}
          disabled={busy || !validation || validation.overall === "BLOCKED"}
        >
          Generate
        </Button>
        <Button
          variant="secondary"
          onClick={handleExportExcel}
          disabled={exporting !== null || selectedVips.length === 0}
        >
          {exporting === "excel" ? "Exporting…" : "Export to Excel"}
        </Button>
        <Button
          variant="secondary"
          onClick={handleExportSop}
          disabled={exporting !== null || selectedVips.length === 0}
        >
          {exporting === "sop" ? "Exporting…" : "Download SOP (.docx)"}
        </Button>
        {error && <span className="text-sm text-red-600 self-center">{error}</span>}
      </div>

      {validation && <ValidationChecklist result={validation} />}
      {generated && <GeneratedOutput result={generated} />}
    </div>
  );
}
