import { useValidatedSession, useHealthCheck } from "../api/queries";
import type { ValidationCheck } from "../api/types";
import { Card, EmptyState, PageHeader, SeverityBadge } from "../components/ui";

const OVERALL_COPY: Record<string, { label: string; color: string }> = {
  CLEAN: { label: "CLEAN", color: "var(--success-strong)" },
  MINOR_FINDINGS: { label: "MINOR FINDINGS", color: "var(--warn-strong)" },
  NEEDS_ATTENTION: { label: "NEEDS ATTENTION", color: "var(--danger-strong)" },
};

function CheckRow({ check }: { check: ValidationCheck }) {
  return (
    <div className="flex items-start justify-between gap-3 text-sm py-2.5 border-b border-slate-50 last:border-0">
      <div className="min-w-0">
        <div className="text-slate-700 font-medium">{check.label}</div>
        <div className="text-xs text-slate-400 mt-0.5">{check.details}</div>
        {check.affected.length > 0 && (
          <ul className="text-xs text-slate-400 list-disc list-inside mt-1 space-y-0.5">
            {check.affected.slice(0, 8).map((a) => (
              <li key={a} className="break-all">
                {a}
              </li>
            ))}
            {check.affected.length > 8 && <li>… and {check.affected.length - 8} more</li>}
          </ul>
        )}
      </div>
      <SeverityBadge severity={check.severity} />
    </div>
  );
}

export function HealthCheckPage() {
  const { sessionId, session } = useValidatedSession();
  const { data, isLoading, isError } = useHealthCheck(sessionId);

  if (!sessionId) {
    return (
      <div>
        <PageHeader title="Config Health Check" />
        <EmptyState title="No session selected" subtitle="Pick a session from the top bar first." />
      </div>
    );
  }

  const overall = data ? OVERALL_COPY[data.overall] : null;
  const findings = data?.checks.filter((c) => c.severity !== "pass") ?? [];
  const passing = data?.checks.filter((c) => c.severity === "pass") ?? [];

  return (
    <div>
      <PageHeader
        title="Config Health Check"
        subtitle={`Heuristic checks against ${session?.name ?? "this session"}'s parsed config — the same spirit as what F5 TAC runs iHealth for, scoped to what this app actually parses. Real, explainable conditions only — nothing from a proprietary known-issues database.`}
      />

      {isLoading && <div className="text-sm text-slate-400">Running checks…</div>}
      {isError && <EmptyState title="Couldn't run the health check" subtitle="Try reselecting the session." />}

      {data && (
        <>
          <Card className="p-4 mb-4 flex items-center justify-between">
            <div>
              <div className="text-xs uppercase tracking-wide text-slate-400">Overall</div>
              <div className="text-lg font-semibold" style={{ color: overall?.color }}>
                {overall?.label}
              </div>
            </div>
            <div className="text-sm text-slate-500">
              {findings.length === 0
                ? `All ${data.checks.length} checks passed`
                : `${findings.length} of ${data.checks.length} check${data.checks.length === 1 ? "" : "s"} flagged something`}
            </div>
          </Card>

          {findings.length > 0 && (
            <Card className="p-4 mb-4">
              <div className="text-sm font-medium text-slate-800 mb-1">Findings</div>
              <div>
                {findings.map((c) => (
                  <CheckRow key={c.id} check={c} />
                ))}
              </div>
            </Card>
          )}

          {passing.length > 0 && (
            <Card className="p-4">
              <div className="text-sm font-medium text-slate-800 mb-1">Passing</div>
              <div>
                {passing.map((c) => (
                  <CheckRow key={c.id} check={c} />
                ))}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
