import { create } from "zustand";

interface OnboardingUiState {
  isChaosDrawerOpen: boolean;
  injectedDelayMs: number;
  injectKyc503: boolean;
  toggleChaosDrawer: () => void;
  setInjectedDelayMs: (ms: number) => void;
  setInjectKyc503: (enabled: boolean) => void;
}

export const useOnboardingUiStore = create<OnboardingUiState>((set) => ({
  isChaosDrawerOpen: false,
  injectedDelayMs: 0,
  injectKyc503: false,
  toggleChaosDrawer: () =>
    set((state) => ({ isChaosDrawerOpen: !state.isChaosDrawerOpen })),
  setInjectedDelayMs: (ms) => set({ injectedDelayMs: ms }),
  setInjectKyc503: (enabled) => set({ injectKyc503: enabled }),
}));