import axios from "axios";
import type {
  GenerateResult,
  MigrationPlan,
  NodeObj,
  Pool,
  SelectionCounts,
  SessionOut,
  Vip,
  ValidationResult,
  Vlan,
} from "./types";
import { toast } from "../components/toastStore";

const http = axios.create({ baseURL: "/api/v1" });

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
    if (!isExpected404Get) {
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
};
