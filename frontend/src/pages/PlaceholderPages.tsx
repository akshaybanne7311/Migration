import { Link } from "react-router-dom";
import { Button, Card, PageHeader } from "../components/ui";

function StandalonePlaceholder({ title, note }: { title: string; note: string }) {
  return (
    <div>
      <PageHeader title={title} />
      <Card className="p-6 max-w-xl">
        <p className="text-sm text-slate-600">{note}</p>
        <div className="mt-4">
          <Link to="/smart-migration">
            <Button variant="secondary">Open Smart Migration</Button>
          </Link>
        </div>
      </Card>
    </div>
  );
}

export function ChangeSetPage() {
  return (
    <StandalonePlaceholder
      title="Change Set"
      note="Change sets are built as part of the Smart Migration wizard (Steps 3–4: Choose Changes and Individual Exceptions). A standalone change-set browser isn't built yet."
    />
  );
}

export function TmshGeneratorPage() {
  return (
    <StandalonePlaceholder
      title="TMSH Generator"
      note="TMSH, REST, and AS3 output are generated from Step 5 of the Smart Migration wizard, once a plan validates as READY."
    />
  );
}

export function ExportPage() {
  return (
    <StandalonePlaceholder
      title="Export"
      note="Copy or download generated TMSH/REST/AS3 from Step 5 of the Smart Migration wizard."
    />
  );
}

export function SearchPage() {
  return (
    <StandalonePlaceholder
      title="Search"
      note="Use the search box on the VIPs page to find a VIP by name or IP for now."
    />
  );
}

export function DependenciesPage() {
  return (
    <StandalonePlaceholder
      title="Dependencies"
      note="A visual dependency graph browser isn't built yet. Node sharing across pools/VIPs is visible on the Nodes page (shared nodes are flagged)."
    />
  );
}

export function ComparePage() {
  return (
    <StandalonePlaceholder
      title="Compare"
      note="Session-to-session comparison isn't built yet."
    />
  );
}
