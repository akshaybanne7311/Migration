import { useState } from "react";
import { Link } from "react-router-dom";
import { useValidatedSession } from "../api/queries";
import { Button, Card, EmptyState, PageHeader } from "../components/ui";
import { toast } from "../components/toastStore";
import { exportFullSessionToExcel } from "../utils/fullSessionExport";
import { exportHldDocument } from "../utils/designDocsExport";

export function ExportPage() {
  const { sessionId, session } = useValidatedSession();
  const [exporting, setExporting] = useState<"excel" | "hld" | null>(null);

  async function handleExport() {
    if (!sessionId) return;
    setExporting("excel");
    try {
      await exportFullSessionToExcel({ sessionId, sessionName: session?.name ?? "session" });
      toast("success", "Full session workbook downloaded.");
    } catch (e) {
      toast("error", e instanceof Error ? e.message : "Export failed");
    } finally {
      setExporting(null);
    }
  }

  async function handleHld() {
    if (!sessionId) return;
    setExporting("hld");
    try {
      await exportHldDocument({ sessionId, sessionName: session?.name ?? "session" });
      toast("success", "HLD document downloaded.");
    } catch (e) {
      toast("error", e instanceof Error ? e.message : "HLD export failed");
    } finally {
      setExporting(null);
    }
  }

  if (!sessionId) {
    return (
      <div>
        <PageHeader title="Export" />
        <EmptyState title="No session selected" subtitle="Pick a session from the top bar first." />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Export"
        subtitle={`Every real data point Config Intelligence recovered from ${session?.name ?? "this session"}'s archive, in one Excel workbook -- not just the current migration plan.`}
      />

      <Card className="p-6 max-w-2xl">
        <div className="text-sm font-medium text-slate-800 mb-2">Full Session Export (.xlsx)</div>
        <p className="text-sm text-slate-600 mb-4">
          One workbook, one sheet per category: Virtual Servers, Pools &amp; Members, Nodes, VLANs, Monitors, Self
          IPs, Trunks, Routes, Route Domains, DNS Resolvers, SSL Certificates, License &amp; License History,
          Software Version, Platform, Device Identity, HA/Traffic Groups, NTP/SNMP/Syslog, Resource Provisioning,
          Profiles &amp; Persistence, iRules, Change History (commands), Change History (config diffs), and the
          Health Check results.
        </p>
        <p className="text-xs text-slate-500 mb-4">
          Command history and config diffs are already redacted server-side before this export runs — passwords,
          passphrases, and shared secrets never appear in the file. Private keys and OS credential files
          (/etc/shadow, filestore *.key) were never parsed by this tool in the first place, so there's nothing
          to accidentally include here either.
        </p>
        <Button onClick={handleExport} disabled={exporting !== null}>
          {exporting === "excel" ? "Building workbook…" : "Download Full Session Export"}
        </Button>
      </Card>

      <Card className="p-6 max-w-2xl mt-4">
        <div className="text-sm font-medium text-slate-800 mb-2">High-Level Design (HLD) — .docx</div>
        <p className="text-sm text-slate-600 mb-4">
          Architecture-level document: source environment (platform, license, software version), current-state
          network topology, risk assessment (from the health check), assumptions/constraints, and the high-level
          migration approach. Session-scoped — doesn't need a migration plan.
        </p>
        <Button onClick={handleHld} disabled={exporting !== null} variant="secondary">
          {exporting === "hld" ? "Building document…" : "Download HLD"}
        </Button>
      </Card>

      <Card className="p-6 max-w-2xl mt-4">
        <div className="text-sm font-medium text-slate-800 mb-2">Migration Plan Export</div>
        <p className="text-sm text-slate-600 mb-4">
          For a plan-scoped export — Excel workbook, SOP, Low-Level Design (LLD), or the generated
          TMSH/REST/AS3/Ansible output — use Step 5 of the Smart Migration wizard, once your plan validates.
        </p>
        <Link to="/smart-migration">
          <Button variant="secondary">Open Smart Migration</Button>
        </Link>
      </Card>
    </div>
  );
}
