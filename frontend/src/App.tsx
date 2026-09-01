import { Route, Routes } from "react-router-dom";
import { AppShell } from "./layout/AppShell";
import { DashboardPage } from "./pages/Dashboard";
import { UploadPage } from "./pages/Upload";
import { SessionsPage } from "./pages/Sessions";
import { VipsPage } from "./pages/VipsPage";
import { PoolsPage } from "./pages/PoolsPage";
import { NodesPage } from "./pages/NodesPage";
import { SystemConfigPage } from "./pages/SystemConfigPage";
import { GuiPreviewPage } from "./pages/GuiPreviewPage";
import { SmartMigrationPage } from "./pages/SmartMigrationPage";
import {
  ChangeSetPage,
  ComparePage,
  DependenciesPage,
  ExportPage,
  SearchPage,
  TmshGeneratorPage,
} from "./pages/PlaceholderPages";

export default function App() {
  return (
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
        <Route path="/smart-migration" element={<SmartMigrationPage />} />
        <Route path="/change-set" element={<ChangeSetPage />} />
        <Route path="/tmsh-generator" element={<TmshGeneratorPage />} />
        <Route path="/export" element={<ExportPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/dependencies" element={<DependenciesPage />} />
        <Route path="/compare" element={<ComparePage />} />
      </Routes>
    </AppShell>
  );
}
