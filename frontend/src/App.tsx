import { Route, Routes } from "react-router-dom";
import { AppShell } from "./layout/AppShell";
import { AmbientBackground } from "./components/AmbientBackground";
import { DashboardPage } from "./pages/Dashboard";
import { UploadPage } from "./pages/Upload";
import { SessionsPage } from "./pages/Sessions";
import { VipsPage } from "./pages/VipsPage";
import { PoolsPage } from "./pages/PoolsPage";
import { NodesPage } from "./pages/NodesPage";
import { SystemConfigPage } from "./pages/SystemConfigPage";
import { GuiPreviewPage } from "./pages/GuiPreviewPage";
import { HealthCheckPage } from "./pages/HealthCheckPage";
import { ChangeHistoryPage } from "./pages/ChangeHistoryPage";
import { SmartMigrationPage } from "./pages/SmartMigrationPage";
import { ExportPage } from "./pages/ExportPage";
import {
  ChangeSetPage,
  ComparePage,
  DependenciesPage,
  SearchPage,
  TmshGeneratorPage,
} from "./pages/PlaceholderPages";

export default function App() {
  return (
    <>
      <AmbientBackground />
      <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/sessions" element={<SessionsPage />} />
        <Route path="/vips" element={<VipsPage />} />
        <Route path="/pools" element={<PoolsPage />} />
        <Route path="/nodes" element={<NodesPage />} />
        <Route path="/system-config" element={<SystemConfigPage />} />
        <Route path="/gui-preview" element={<GuiPreviewPage />} />
        <Route path="/health-check" element={<HealthCheckPage />} />
        <Route path="/change-history" element={<ChangeHistoryPage />} />
        <Route path="/smart-migration" element={<SmartMigrationPage />} />
        <Route path="/change-set" element={<ChangeSetPage />} />
        <Route path="/tmsh-generator" element={<TmshGeneratorPage />} />
        <Route path="/export" element={<ExportPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/dependencies" element={<DependenciesPage />} />
        <Route path="/compare" element={<ComparePage />} />
      </Routes>
      </AppShell>
    </>
  );
}
