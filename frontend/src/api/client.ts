import axios from "axios";
import type {
  CommandHistoryListOut,
  CsvImportResult,
  CsvImportType,
  GenerateResult,
  HealthCheckResult,
  MigrationPlan,
  Monitor,
  NodeObj,
  Pool,
  SelectionCounts,
  SessionOut,
  SystemObject,
  Vip,
  ValidationResult,
  Vlan,
} from "./types";
import { toast } from "../components/toastStore";

const API_BASE = "/api/v1";
const http = axios.create({ baseURL: API_BASE });

function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (!error.response) {
      return "Can't reach the server. Check that the backend is running.";
    }
    const detail = error.response.data?.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      return String((detail as { message: unknown }).message);
    }
    return `Request failed (HTTP ${error.response.status})`;
  }
  return error instanceof Error ? error.message : "Unexpected error";
}

http.interceptors.response.use(
  (response) => response,
  (error) => {
    // A 404 on a GET is often an expected "not found yet" probe (e.g. a
    // session that was just deleted); don't spam a toast for those. Every
    // other failure — write operations, validation/generate errors,
    // network drops, 5xxs — gets surfaced globally so nothing fails
    // silently off-screen from wherever the user happens to be looking.
    const isExpected404Get = error?.response?.status === 404 && error?.config?.method === "get";
    // The health check polls every 30s specifically to show a live
    // connected/disconnected indicator -- that indicator IS the surfaced
    // failure; toasting on top of it would repeat every 30s for as long
    // as the backend stays down.
    const isHealthPoll = typeof error?.config?.url === "string" && error.config.url.includes("/health");
    if (!isExpected404Get && !isHealthPoll) {
      toast("error", extractErrorMessage(error));
    }
    return Promise.reject(error);
  },
);

export const api = {
  // sessions
  listSessions: () => http.get<SessionOut[]>("/sessions").then((r) => r.data),
  getSession: (id: string) => http.get<SessionOut>(`/sessions/${id}`).then((r) => r.data),
  uploadSession: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return http
      .post<SessionOut>("/sessions", form, { headers: { "Content-Type": "multipart/form-data" } })
      .then((r) => r.data);
  },
  deleteSession: (id: string) => http.delete(`/sessions/${id}`).then((r) => r.data),

  // vips
  listVips: (sessionId: string, search?: string) =>
    http
      .get<{ items: Vip[]; total: number }>(`/sessions/${sessionId}/vips`, {
        params: { search: search || undefined, limit: 500 },
      })
      .then((r) => r.data),
  getVipDetail: (sessionId: string, name: string) =>
    http.get<Vip>(`/sessions/${sessionId}/vips/detail`, { params: { name } }).then((r) => r.data),
  selectionKpis: (sessionId: string, vipNames: string[]) =>
    http
      .post<SelectionCounts>(`/sessions/${sessionId}/vips/kpis`, { vip_names: vipNames })
      .then((r) => r.data),

  // pools
  listPools: (sessionId: string) =>
    http.get<{ items: Pool[]; total: number }>(`/sessions/${sessionId}/pools`).then((r) => r.data),
  getPoolDetail: (sessionId: string, name: string) =>
    http.get<Pool>(`/sessions/${sessionId}/pools/detail`, { params: { name } }).then((r) => r.data),

  // nodes
  listNodes: (sessionId: string) =>
    http
      .get<{ items: NodeObj[]; total: number }>(`/sessions/${sessionId}/nodes`)
      .then((r) => r.data),

  // vlans
  listVlans: (sessionId: string) =>
    http.get<{ items: Vlan[]; total: number }>(`/sessions/${sessionId}/vlans`).then((r) => r.data),
  listMonitors: (sessionId: string) =>
    http.get<{ items: Monitor[]; total: number }>(`/sessions/${sessionId}/monitors`).then((r) => r.data),
  listSystemObjects: (sessionId: string) =>
    http
      .get<{ items: SystemObject[]; total: number }>(`/sessions/${sessionId}/system-objects`)
      .then((r) => r.data),

  // health
  health: () => http.get<{ status: string; version: string }>("/health").then((r) => r.data),
  runHealthCheck: (sessionId: string) =>
    http.get<HealthCheckResult>(`/sessions/${sessionId}/health-check`).then((r) => r.data),
  listCommandHistory: (sessionId: string, opts?: { mutatingOnly?: boolean; user?: string }) =>
    http
      .get<CommandHistoryListOut>(`/sessions/${sessionId}/command-history`, {
        params: { mutating_only: opts?.mutatingOnly ?? undefined, user: opts?.user ?? undefined },
      })
      .then((r) => r.data),
  certificateDownloadUrl: (sessionId: string, fingerprint: string) =>
    `${API_BASE}/sessions/${sessionId}/certificates/${fingerprint}/download`,

  // migration plans
  createPlan: (sessionId: string, plan: MigrationPlan) =>
    http
      .post<{ id: string; plan: MigrationPlan }>(`/sessions/${sessionId}/migration-plans`, plan)
      .then((r) => r.data),
  updatePlan: (sessionId: string, planId: string, plan: MigrationPlan, step: number) =>
    http
      .put<{ id: string; plan: MigrationPlan }>(
        `/sessions/${sessionId}/migration-plans/${planId}`,
        plan,
        { params: { step } },
      )
      .then((r) => r.data),
  validatePlan: (sessionId: string, planId: string) =>
    http
      .post<ValidationResult>(`/sessions/${sessionId}/migration-plans/${planId}/validate`)
      .then((r) => r.data),
  generatePlan: (sessionId: string, planId: string) =>
    http
      .post<GenerateResult>(`/sessions/${sessionId}/migration-plans/${planId}/generate`)
      .then((r) => r.data),
  importCsv: (sessionId: string, csvType: CsvImportType, selectedVips: string[], file: File) => {
    const form = new FormData();
    form.append("csv_type", csvType);
    form.append("selected_vips", selectedVips.join(","));
    form.append("file", file);
    return http
      .post<CsvImportResult>(`/sessions/${sessionId}/migration-plans/import-csv`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },
};
