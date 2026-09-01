import { WizardShell } from "../features/smart-migration/wizard/WizardShell";
import { PageHeader } from "../components/ui";

export function SmartMigrationPage() {
  return (
    <div>
      <PageHeader
        title="Smart Migration"
        subtitle="Select VIPs, review their configuration, choose changes, then validate and generate."
      />
      <WizardShell />
    </div>
  );
}
