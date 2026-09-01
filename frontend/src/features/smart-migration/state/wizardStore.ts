import { create } from "zustand";
import type { ChangeType, CommonChange, NodeChange, OutputMode, PoolMemberEdit, VipException } from "../../../api/types";

interface WizardState {
  sessionId: string | null;
  step: number;
  selectedVipNames: Set<string>;
  search: string;

  chosenChangeTypes: Set<ChangeType>;
  commonChanges: Partial<Record<ChangeType, CommonChange>>;
  nodeChanges: NodeChange[];
  poolMemberEdits: PoolMemberEdit[];
  exceptions: VipException[];
  createNetworkObjects: boolean;
  outputMode: OutputMode;

  planId: string | null;

  resetForSession: (sessionId: string | null) => void;
  setStep: (step: number) => void;
  setSearch: (search: string) => void;
  toggleVip: (name: string) => void;
  setAllVips: (names: string[], checked: boolean) => void;
  clearSelection: () => void;

  toggleChangeType: (ct: ChangeType) => void;
  setCommonChange: (ct: ChangeType, payload: Record<string, unknown>) => void;
  removeCommonChange: (ct: ChangeType) => void;

  setNodeChanges: (changes: NodeChange[]) => void;
  setPoolMemberEdits: (edits: PoolMemberEdit[]) => void;
  setExceptions: (exceptions: VipException[]) => void;
  setCreateNetworkObjects: (v: boolean) => void;
  setOutputMode: (mode: OutputMode) => void;
  setPlanId: (id: string | null) => void;
}

export const useWizardStore = create<WizardState>((set, get) => ({
  sessionId: null,
  step: 1,
  selectedVipNames: new Set(),
  search: "",

  chosenChangeTypes: new Set(),
  commonChanges: {},
  nodeChanges: [],
  poolMemberEdits: [],
  exceptions: [],
  createNetworkObjects: false,
  outputMode: "changes_only",

  planId: null,

  resetForSession: (sessionId) =>
    set({
      sessionId,
      step: 1,
      selectedVipNames: new Set(),
      search: "",
      chosenChangeTypes: new Set(),
      commonChanges: {},
      nodeChanges: [],
      poolMemberEdits: [],
      exceptions: [],
      createNetworkObjects: false,
      outputMode: "changes_only",
      planId: null,
    }),

  setStep: (step) => set({ step }),
  setSearch: (search) => set({ search }),

  toggleVip: (name) => {
    const next = new Set(get().selectedVipNames);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    set({ selectedVipNames: next });
  },
  setAllVips: (names, checked) => {
    const next = new Set(get().selectedVipNames);
    for (const n of names) {
      if (checked) next.add(n);
      else next.delete(n);
    }
    set({ selectedVipNames: next });
  },
  clearSelection: () => set({ selectedVipNames: new Set() }),

  toggleChangeType: (ct) => {
    const next = new Set(get().chosenChangeTypes);
    if (next.has(ct)) {
      next.delete(ct);
      const commonChanges = { ...get().commonChanges };
      delete commonChanges[ct];
      set({ chosenChangeTypes: next, commonChanges });
    } else {
      next.add(ct);
      set({ chosenChangeTypes: next });
    }
  },
  setCommonChange: (ct, payload) =>
    set({ commonChanges: { ...get().commonChanges, [ct]: { change_type: ct, payload } } }),
  removeCommonChange: (ct) => {
    const commonChanges = { ...get().commonChanges };
    delete commonChanges[ct];
    set({ commonChanges });
  },

  setNodeChanges: (nodeChanges) => set({ nodeChanges }),
  setPoolMemberEdits: (poolMemberEdits) => set({ poolMemberEdits }),
  setExceptions: (exceptions) => set({ exceptions }),
  setCreateNetworkObjects: (v) => set({ createNetworkObjects: v }),
  setOutputMode: (outputMode) => set({ outputMode }),
  setPlanId: (planId) => set({ planId }),
}));
