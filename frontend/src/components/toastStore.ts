import { create } from "zustand";

export type ToastKind = "error" | "warn" | "success" | "info";

export interface Toast {
  id: string;
  kind: ToastKind;
  message: string;
}

interface ToastState {
  toasts: Toast[];
  push: (kind: ToastKind, message: string) => void;
  dismiss: (id: string) => void;
}

const AUTO_DISMISS_MS: Record<ToastKind, number> = {
  error: 8000,
  warn: 6000,
  success: 4000,
  info: 4000,
};

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  push: (kind, message) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    // Collapse exact-duplicate messages already on screen (e.g. a request
    // that fails twice in a row from a double-click) instead of stacking
    // identical toasts.
    if (get().toasts.some((t) => t.kind === kind && t.message === message)) return;
    set({ toasts: [...get().toasts, { id, kind, message }] });
    window.setTimeout(() => get().dismiss(id), AUTO_DISMISS_MS[kind]);
  },
  dismiss: (id) => set({ toasts: get().toasts.filter((t) => t.id !== id) }),
}));

export function toast(kind: ToastKind, message: string) {
  useToastStore.getState().push(kind, message);
}
