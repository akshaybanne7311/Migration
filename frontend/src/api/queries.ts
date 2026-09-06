import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { create } from "zustand";
import { api } from "./client";

interface SessionState {
  currentSessionId: string | null;
  setCurrentSessionId: (id: string | null) => void;
}

const STORAGE_KEY = "f5ci.currentSessionId";

export const useSessionStore = create<SessionState>((set) => ({
  currentSessionId: localStorage.getItem(STORAGE_KEY),
  setCurrentSessionId: (id) => {
    if (id) localStorage.setItem(STORAGE_KEY, id);
    else localStorage.removeItem(STORAGE_KEY);
    set({ currentSessionId: id });
  },
}));

/** Validates the persisted session id still exists server-side; clears it
 * (and every cached query under it) if it was deleted elsewhere -- this is
 * the guarantee that a stale/deleted session can never silently render as
 * "current" after a reload.
 */
export function useValidatedSession() {
  const { currentSessionId, setCurrentSessionId } = useSessionStore();
  const queryClient = useQueryClient();

  const sessionQuery = useQuery({
    queryKey: ["session", currentSessionId],
    queryFn: () => api.getSession(currentSessionId as string),
    enabled: !!currentSessionId,
    retry: false,
  });

  useEffect(() => {
    if (sessionQuery.isError && currentSessionId) {
      queryClient.removeQueries({ queryKey: ["session", currentSessionId] });
      setCurrentSessionId(null);
    }
  }, [sessionQuery.isError, currentSessionId, queryClient, setCurrentSessionId]);

  return {
    sessionId: sessionQuery.isError ? null : currentSessionId,
    session: sessionQuery.data ?? null,
    isLoading: sessionQuery.isLoading,
  };
}

export function useSessionsList() {
  return useQuery({ queryKey: ["sessions"], queryFn: api.listSessions });
}

export function useHealthCheck(sessionId: string | null) {
  return useQuery({
    queryKey: ["session", sessionId, "health-check"],
    queryFn: () => api.runHealthCheck(sessionId as string),
    enabled: !!sessionId,
  });
}

export function useCommandHistory(sessionId: string | null, opts?: { mutatingOnly?: boolean; user?: string }) {
  return useQuery({
    queryKey: ["session", sessionId, "command-history", opts?.mutatingOnly ?? false, opts?.user ?? null],
    queryFn: () => api.listCommandHistory(sessionId as string, opts),
    enabled: !!sessionId,
  });
}

export function useConfigRevisions(sessionId: string | null, opts?: { configFile?: string }) {
  return useQuery({
    queryKey: ["session", sessionId, "config-revisions", opts?.configFile ?? null],
    queryFn: () => api.listConfigRevisions(sessionId as string, opts),
    enabled: !!sessionId,
  });
}

export function useBackendHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    retry: false,
    refetchInterval: 30000,
  });
}

export function useVips(sessionId: string | null, search?: string) {
  return useQuery({
    queryKey: ["session", sessionId, "vips", search ?? ""],
    queryFn: () => api.listVips(sessionId as string, search),
    enabled: !!sessionId,
  });
}

export function usePools(sessionId: string | null) {
  return useQuery({
    queryKey: ["session", sessionId, "pools"],
    queryFn: () => api.listPools(sessionId as string),
    enabled: !!sessionId,
  });
}

export function useNodes(sessionId: string | null) {
  return useQuery({
    queryKey: ["session", sessionId, "nodes"],
    queryFn: () => api.listNodes(sessionId as string),
    enabled: !!sessionId,
  });
}

export function useVlans(sessionId: string | null) {
  return useQuery({
    queryKey: ["session", sessionId, "vlans"],
    queryFn: () => api.listVlans(sessionId as string),
    enabled: !!sessionId,
  });
}

export function useMonitors(sessionId: string | null) {
  return useQuery({
    queryKey: ["session", sessionId, "monitors"],
    queryFn: () => api.listMonitors(sessionId as string),
    enabled: !!sessionId,
  });
}

export function useSystemObjects(sessionId: string | null) {
  return useQuery({
    queryKey: ["session", sessionId, "system-objects"],
    queryFn: () => api.listSystemObjects(sessionId as string),
    enabled: !!sessionId,
  });
}

export function useSelectionKpis(sessionId: string | null, vipNames: string[]) {
  return useQuery({
    queryKey: ["session", sessionId, "kpis", [...vipNames].sort()],
    queryFn: () => api.selectionKpis(sessionId as string, vipNames),
    enabled: !!sessionId && vipNames.length > 0,
  });
}
