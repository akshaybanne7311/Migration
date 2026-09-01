import { useEffect } from "react";
import { useValidatedSession } from "../../../api/queries";
import { Button, EmptyState } from "../../../components/ui";
import { Step1SelectVips } from "../steps/Step1SelectVips";
import { Step2ReviewConfig } from "../steps/Step2ReviewConfig";
import { Step3ChooseChanges } from "../steps/Step3ChooseChanges";
import { Step4CommonAndExceptions } from "../steps/Step4CommonAndExceptions";
import { Step5ValidateGenerate } from "../steps/Step5ValidateGenerate";
import { useWizardStore } from "../state/wizardStore";

const STEPS = [
  { n: 1, label: "Select VIPs" },
  { n: 2, label: "Review Configuration" },
  { n: 3, label: "Choose Changes" },
  { n: 4, label: "Individual Exceptions" },
  { n: 5, label: "Validate & Generate" },
];

function StepIndicator({ step, onJump }: { step: number; onJump: (n: number) => void }) {
  return (
    <div className="flex items-center gap-1 mb-6">
      {STEPS.map((s, idx) => (
        <div key={s.n} className="flex items-center">
          <button
            onClick={() => onJump(s.n)}
            className={`neon-btn flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-all duration-200 ${
              s.n === step
                ? "bg-blue-600 text-white font-medium"
                : s.n < step
                  ? "text-blue-700 hover:bg-blue-50"
                  : "text-slate-400"
            }`}
            style={s.n === step ? { animation: "neonPulse 2.2s ease-in-out infinite" } : undefined}
          >
            <span
              className={`h-5 w-5 rounded-full flex items-center justify-center text-[11px] transition-colors ${
                s.n === step ? "bg-white/20" : s.n < step ? "bg-blue-100" : "bg-slate-100"
              }`}
            >
              {s.n < step ? "✓" : s.n}
            </span>
            {s.label}
          </button>
          {idx < STEPS.length - 1 && (
            <span
              className="w-4 h-px mx-1 transition-colors duration-300"
              style={{
                background: s.n < step ? "linear-gradient(90deg, var(--cyan), var(--violet))" : "var(--border)",
                boxShadow: s.n < step ? "var(--glow-cyan)" : "none",
              }}
            />
          )}
        </div>
      ))}
    </div>
  );
}

export function WizardShell() {
  const { sessionId } = useValidatedSession();
  const step = useWizardStore((s) => s.step);
  const setStep = useWizardStore((s) => s.setStep);
  const storeSessionId = useWizardStore((s) => s.sessionId);
  const resetForSession = useWizardStore((s) => s.resetForSession);
  const selectedVipNames = useWizardStore((s) => s.selectedVipNames);

  useEffect(() => {
    if (sessionId !== storeSessionId) {
      resetForSession(sessionId);
    }
  }, [sessionId, storeSessionId, resetForSession]);

  if (!sessionId) {
    return <EmptyState title="No session selected" subtitle="Pick a session from the top bar to begin." />;
  }

  const canProceedFrom1 = selectedVipNames.size > 0;

  return (
    <div>
      <StepIndicator step={step} onJump={(n) => (n === 1 || canProceedFrom1) && setStep(n)} />

      <div className="mb-6">
        {step === 1 && <Step1SelectVips />}
        {step === 2 && <Step2ReviewConfig />}
        {step === 3 && <Step3ChooseChanges />}
        {step === 4 && <Step4CommonAndExceptions />}
        {step === 5 && <Step5ValidateGenerate />}
      </div>

      <div className="flex justify-between">
        <Button variant="secondary" disabled={step === 1} onClick={() => setStep(step - 1)}>
          Back
        </Button>
        <Button
          disabled={step === 5 || (step === 1 && !canProceedFrom1)}
          onClick={() => setStep(step + 1)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
