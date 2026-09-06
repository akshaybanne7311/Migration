import { Link } from "react-router-dom";
import { useValidatedSession } from "../api/queries";
import { Button, Card, KpiCard, PageHeader, useCountUp } from "../components/ui";

const PIPELINE_STEPS = [
  "UCS / QKView / bigip.conf",
  "Tokenizer → recursive-descent parser",
  "Dependency graph (nodes, pools, VLANs deduped)",
  "Smart Migration wizard",
  "TMSH / REST / AS3, one resolved plan",
];

const STATS = [
  { value: 3, label: "Output formats — TMSH · REST · AS3" },
  { value: 9, label: "Validation checks before you generate" },
  { value: 118, label: "Automated backend tests" },
  { value: 0, label: "Manual TMSH scripting required" },
];

function Stat({ value, label }: { value: number; label: string }) {
  const animated = useCountUp(value, 900);
  return (
    <div className="px-4 py-6 border-r last:border-r-0" style={{ borderColor: "var(--border-faint)" }}>
      <div
        className="font-display text-3xl font-bold text-slate-900"
        style={{ color: "var(--cyan-bright)", textShadow: "var(--kpi-glow)" }}
      >
        {animated}
      </div>
      <div className="font-mono-neon text-[10px] text-slate-500 mt-1.5 uppercase tracking-wide leading-relaxed">
        {label}
      </div>
    </div>
  );
}

function StatsBar() {
  return (
    <div
      className="stagger-children grid grid-cols-2 sm:grid-cols-4 border-t"
      style={{ borderColor: "var(--border-faint)" }}
    >
      {STATS.map((s) => (
        <Stat key={s.label} value={s.value} label={s.label} />
      ))}
    </div>
  );
}

function PipelinePanel() {
  return (
    <Card className="p-6 animate-float">
      <div className="font-mono-neon text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-400 mb-4">
        Pipeline
      </div>
      <div className="space-y-0">
        {PIPELINE_STEPS.map((step, i) => (
          <div key={step} className="flex items-start gap-3 pb-3 last:pb-0">
            <div className="flex flex-col items-center shrink-0">
              <span
                className="h-1.5 w-1.5 rounded-sm mt-1.5"
                style={{ background: "var(--cyan)", boxShadow: "var(--glow-cyan)" }}
              />
              {i < PIPELINE_STEPS.length - 1 && (
                <span className="w-px flex-1 mt-1" style={{ background: "var(--border)" }} />
              )}
            </div>
            <div className="font-mono-neon text-xs text-slate-500 pt-0.5">{step}</div>
          </div>
        ))}
      </div>
      <div
        className="flex justify-between mt-5 pt-4 border-t font-mono-neon text-[10px] font-semibold uppercase tracking-wide"
        style={{ borderColor: "var(--border-faint)", color: "var(--cyan)" }}
      >
        <span>01 Ingest</span>
        <span>02 Plan</span>
        <span>03 Generate</span>
      </div>
    </Card>
  );
}

export function DashboardPage() {
  const { sessionId, session } = useValidatedSession();

  if (!sessionId || !session) {
    return (
      <div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 items-center min-h-[calc(100vh-260px)]">
          <div className="stagger-children">
            <div className="flex items-center gap-2 mb-3">
              <span
                className="h-2 w-2 rounded-sm shrink-0"
                style={{ background: "var(--cyan)", boxShadow: "var(--glow-cyan)" }}
              />
              <span className="font-mono-neon text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                Dependency-aware migration
              </span>
            </div>
            <h1 className="font-display text-4xl sm:text-5xl font-bold text-slate-900 tracking-tight leading-[1.05]">
              Plan BIG-IP migrations without the guesswork.
            </h1>
            <p className="text-sm text-slate-500 mt-4 max-w-md leading-relaxed">
              Upload a UCS/QKView archive, select the VIPs you're touching, and let the dependency
              engine handle node dedup, pool renames, and safe deletes — while you generate real
              TMSH/REST/AS3 output.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-4">
              <Link to="/upload">
                <Button size="lg">Upload configuration →</Button>
              </Link>
              <Link to="/sessions">
                <Button variant="secondary" size="lg">
                  Browse sessions
                </Button>
              </Link>
            </div>
          </div>
          <PipelinePanel />
        </div>
        <StatsBar />
      </div>
    );
  }

  return (
    <div>
      <PageHeader eyebrow="Workspace" title="Dashboard" subtitle={session.name} />
      <div className="stagger-children flex flex-wrap gap-3 mb-6">
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
          <Button>Go to Smart Migration →</Button>
        </Link>
      </Card>
    </div>
  );
}
