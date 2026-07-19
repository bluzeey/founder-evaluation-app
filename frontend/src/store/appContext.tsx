import { createContext, useContext, useState, useEffect, useCallback } from "react";
import type { Role, User, CaseDecision, CaseStatus } from "@/domain/types";
import type { ReactNode } from "react";

export type CaseOverride = {
  status?: CaseStatus;
  owner?: string;
  nextAction?: string;
  decisions?: CaseDecision[];
};

export type AppState = {
  user: User;
  caseOverrides: Record<string, CaseOverride>;
};

const STORAGE_KEY = "vc-brain-demo-state-v1";

const defaultState: AppState = {
  user: { id: "u-analyst", name: "Jordan Lee", role: "ANALYST" },
  caseOverrides: {},
};

const AppContext = createContext<{
  state: AppState;
  setRole: (role: Role) => void;
  setUserName: (name: string) => void;
  setCaseOverride: (caseId: string, patch: Partial<CaseOverride>) => void;
  recordDecision: (caseId: string, decision: CaseDecision) => void;
  resetDemo: () => void;
} | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AppState>(() => loadState());

  useEffect(() => {
    saveState(state);
  }, [state]);

  const setRole = useCallback((role: Role) => {
    setState((prev) => ({ ...prev, user: { ...prev.user, role } }));
  }, []);

  const setUserName = useCallback((name: string) => {
    setState((prev) => ({ ...prev, user: { ...prev.user, name } }));
  }, []);

  const setCaseOverride = useCallback((caseId: string, patch: Partial<CaseOverride>) => {
    setState((prev) => ({
      ...prev,
      caseOverrides: {
        ...prev.caseOverrides,
        [caseId]: { ...prev.caseOverrides[caseId], ...patch },
      },
    }));
  }, []);

  const recordDecision = useCallback((caseId: string, decision: CaseDecision) => {
    setState((prev) => {
      const existing = prev.caseOverrides[caseId]?.decisions || [];
      return {
        ...prev,
        caseOverrides: {
          ...prev.caseOverrides,
          [caseId]: {
            ...prev.caseOverrides[caseId],
            decisions: [...existing, decision],
          },
        },
      };
    });
  }, []);

  const resetDemo = useCallback(() => {
    setState(defaultState);
  }, []);

  return (
    <AppContext.Provider value={{ state, setRole, setUserName, setCaseOverride, recordDecision, resetDemo }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used inside AppProvider");
  return ctx;
}

export function useRole() {
  return useApp().state.user.role;
}

function loadState(): AppState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultState;
    const parsed = JSON.parse(raw) as AppState;
    return { ...defaultState, ...parsed, user: { ...defaultState.user, ...parsed.user } };
  } catch {
    return defaultState;
  }
}

function saveState(state: AppState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // ignore storage errors
  }
}
