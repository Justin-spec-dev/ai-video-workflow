// UI-only state: dialogs, node search palette, run-in-flight flag.
import { create } from 'zustand';
import type { CostEstimate } from '../types';

interface NodeSearchState {
  open: boolean;
  /** Flow-coordinate position where a chosen node should be inserted. */
  flowX: number;
  flowY: number;
}

interface InspectState {
  open: boolean;
  nodeId: string;
  mode: 'input' | 'output';
}

interface UIStoreState {
  credentialsOpen: boolean;
  setCredentialsOpen: (open: boolean) => void;

  estimateOpen: boolean;
  estimate: CostEstimate | null;
  openEstimate: (estimate: CostEstimate) => void;
  closeEstimate: () => void;

  runBusy: boolean;
  setRunBusy: (busy: boolean) => void;

  nodeSearch: NodeSearchState;
  openNodeSearch: (flowX: number, flowY: number) => void;
  closeNodeSearch: () => void;

  inspect: InspectState | null;
  openInspect: (nodeId: string, mode: 'input' | 'output') => void;
  closeInspect: () => void;

  quickStartOpen: boolean;
  setQuickStartOpen: (open: boolean) => void;

  /** 左侧节点库整栏收起/展开（持久化到 localStorage）。 */
  libraryCollapsed: boolean;
  toggleLibrary: () => void;
}

const LS_LIBRARY = 'aivwf.library_collapsed';

export const useUIStore = create<UIStoreState>((set) => ({
  credentialsOpen: false,
  setCredentialsOpen: (credentialsOpen) => set({ credentialsOpen }),

  estimateOpen: false,
  estimate: null,
  openEstimate: (estimate) => set({ estimateOpen: true, estimate }),
  closeEstimate: () => set({ estimateOpen: false }),

  runBusy: false,
  setRunBusy: (runBusy) => set({ runBusy }),

  nodeSearch: { open: false, flowX: 0, flowY: 0 },
  openNodeSearch: (flowX, flowY) => set({ nodeSearch: { open: true, flowX, flowY } }),
  closeNodeSearch: () => set((s) => ({ nodeSearch: { ...s.nodeSearch, open: false } })),

  inspect: null,
  openInspect: (nodeId, mode) => set({ inspect: { open: true, nodeId, mode } }),
  closeInspect: () => set({ inspect: null }),

  quickStartOpen: false,
  setQuickStartOpen: (quickStartOpen) => set({ quickStartOpen }),

  libraryCollapsed: typeof localStorage !== 'undefined' && localStorage.getItem(LS_LIBRARY) === '1',
  toggleLibrary: () =>
    set((s) => {
      const next = !s.libraryCollapsed;
      try {
        localStorage.setItem(LS_LIBRARY, next ? '1' : '0');
      } catch {
        /* ignore */
      }
      return { libraryCollapsed: next };
    }),
}));
