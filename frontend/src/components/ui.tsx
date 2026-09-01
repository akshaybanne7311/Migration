import type { ReactNode } from "react";
import type { Severity } from "../api/types";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`neon-card bg-white border border-slate-200 rounded-lg shadow-sm ${className}`}>
      {children}
    </div>
  );
}

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-5 animate-page-in">
      <h1 className="font-display text-lg font-semibold text-slate-900">{title}</h1>
      {subtitle && <p className="text-sm text-slate-500 mt-0.5">{subtitle}</p>}
    </div>
  );
}

export function Button({
  children,
  onClick,
  variant = "primary",
  disabled,
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  disabled?: boolean;
  type?: "button" | "submit";
}) {
  const base =
    "neon-btn text-sm font-medium rounded-md px-3 py-1.5 transition-all disabled:opacity-40 disabled:cursor-not-allowed disabled:filter-none";
  const styles: Record<string, string> = {
    primary: "bg-blue-600 text-white hover:bg-blue-700",
    secondary: "bg-white border border-slate-300 text-slate-700 hover:bg-slate-50",
    ghost: "text-slate-600 hover:bg-slate-100",
    danger: "bg-red-600 text-white hover:bg-red-700",
  };
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={`${base} ${styles[variant]}`}>
      {children}
    </button>
  );
}

export function KpiCard({ label, value }: { label: string; value: number | string }) {
  return (
    <Card className="px-4 py-3 min-w-[120px] animate-page-in">
      <div
        className="font-mono-neon text-xl font-semibold text-slate-900 tabular-nums"
        style={{ color: "var(--cyan-bright)", textShadow: "var(--kpi-glow)" }}
      >
        {value}
      </div>
      <div className="text-xs text-slate-500 mt-0.5 uppercase tracking-wide">{label}</div>
    </Card>
  );
}

const severityStyles: Record<Severity, string> = {
  pass: "bg-emerald-50 text-emerald-700 border-emerald-200",
  warn: "bg-amber-50 text-amber-700 border-amber-200",
  blocked: "bg-red-50 text-red-700 border-red-200",
};

const severityDotColor: Record<Severity, string> = {
  pass: "var(--success-strong)",
  warn: "var(--warn-strong)",
  blocked: "var(--danger-strong)",
};

const severityLabels: Record<Severity, string> = {
  pass: "PASS",
  warn: "WARN",
  blocked: "BLOCKED",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-[11px] font-semibold px-2 py-0.5 rounded border ${severityStyles[severity]}`}
    >
      <span className="neon-dot" style={{ background: severityDotColor[severity] }} />
      {severityLabels[severity]}
    </span>
  );
}

export function EmptyState({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <Card className="px-6 py-10 text-center animate-page-in">
      <div className="text-sm font-medium text-slate-600">{title}</div>
      {subtitle && <div className="text-xs text-slate-400 mt-1">{subtitle}</div>}
    </Card>
  );
}

export function Checkbox({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: ReactNode;
}) {
  return (
    <label className="flex items-center gap-2 cursor-pointer select-none">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded border-slate-300 accent-cyan-400 text-blue-600 focus:ring-blue-500"
      />
      <span className="text-sm text-slate-700">{label}</span>
    </label>
  );
}
