import { Link } from "react-router-dom";
import { useValidatedSession } from "../api/queries";
import { Button, Card, EmptyState, KpiCard, PageHeader } from "../components/ui";

export function DashboardPage() {
  const { sessionId, session } = useValidatedSession();

  if (!sessionId || !session) {
    return (
      <div>
        <PageHeader title="Dashboard" />
        <EmptyState
          title="No session selected"
          subtitle="Upload a BIG-IP configuration to begin, or pick an existing session."
        />
        <div className="mt-4 flex gap-3">
          <Link to="/upload">
            <Button>Upload configuration</Button>
          </Link>
          <Link to="/sessions">
            <Button variant="secondary">Browse sessions</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Dashboard" subtitle={session.name} />
      <div className="flex flex-wrap gap-3 mb-6">
        <KpiCard label="VIPs" value={session.vip_count} />
        <KpiCard label="Pools" value={session.pool_count} />
        <KpiCard label="Nodes" value={session.node_count} />
        <KpiCard label="VLANs" value={session.vlan_count} />
      </div>
      <Card className="p-5">
        <div className="text-sm font-medium text-slate-800 mb-2">Get started</div>
        <p className="text-sm text-slate-500 mb-4">
          Use Smart Migration to select VIPs, review their current configuration, choose what
          changes, and generate TMSH/REST/AS3 output.
        </p>
        <Link to="/smart-migration">
          <Button>Go to Smart Migration</Button>
        </Link>
      </Card>
    </div>
  );
}
