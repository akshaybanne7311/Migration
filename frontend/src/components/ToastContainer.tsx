import { useToastStore, type ToastKind } from "./toastStore";

const KIND_STYLES: Record<ToastKind, { border: string; dot: string; label: string }> = {
  error: { border: "border-red-200", dot: "var(--danger-strong)", label: "Error" },
  warn: { border: "border-amber-200", dot: "var(--warn-strong)", label: "Warning" },
  success: { border: "border-emerald-200", dot: "var(--success-strong)", label: "Done" },
  info: { border: "border-slate-200", dot: "var(--cyan-bright)", label: "Info" },
};

export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 max-w-sm w-full pointer-events-none">
      {toasts.map((t) => {
        const style = KIND_STYLES[t.kind];
        return (
          <div
            key={t.id}
            className={`neon-card animate-page-in pointer-events-auto bg-white border ${style.border} rounded-lg shadow-lg px-4 py-3 flex items-start gap-2.5`}
          >
            <span
              className="neon-dot mt-1 shrink-0"
              style={{ background: style.dot }}
            />
            <div className="flex-1 min-w-0">
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                {style.label}
              </div>
              <div className="text-sm text-slate-700 break-words">{t.message}</div>
            </div>
            <button
              onClick={() => dismiss(t.id)}
              className="text-slate-400 hover:text-slate-700 text-sm leading-none shrink-0"
              aria-label="Dismiss notification"
            >
              ×
            </button>
          </div>
        );
      })}
    </div>
  );
}
