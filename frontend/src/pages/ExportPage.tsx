import { useState } from "react";
import { Link } from "react-router-dom";
import { useValidatedSession } from "../api/queries";
import { Button, Card, EmptyState, PageHeader } from "../components/ui";
import { toast } from "../components/toastStore";
import { exportFullSessionToExcel } from "../utils/fullSessionExport";

export function ExportPage() {
  const { sessionId, session } = useValidatedSession();
  const [exporting, setExporting] = useState(false);

  async function handleExport() {
    if (!sessionId) return;
    setExporting(true);
    try {
      await exportFullSessionToExcel({ sessionId, sessionName: session?.name ?? "session" });
      toast("success", "Full session workbook downloaded.");
    } catch (e) {
      toast("error", e instanceof Error ? e.message : "Export failed");
    } finally {
      setExporting(false);
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
        <Button onClick={handleExport} disabled={exporting}>
          {exporting ? "Building workbook…" : "Download Full Session Export"}
        </Button>
      </Card>

      <Card className="p-6 max-w-2xl mt-4">
        <div className="text-sm font-medium text-slate-800 mb-2">Migration Plan Export</div>
        <p className="text-sm text-slate-600 mb-4">
          For a plan-scoped export (selected VIPs, validation results, generated TMSH/REST/AS3/Ansible) — as an
          Excel workbook or an SOP document — use Step 5 of the Smart Migration wizard.
        </p>
        <Link to="/smart-migration">
          <Button variant="secondary">Open Smart Migration</Button>
        </Link>
      </Card>
    </div>
  );
}
