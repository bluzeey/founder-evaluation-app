import { createContext, useContext, useState, useEffect, useCallback, useMemo } from "react";
import { api } from "@/api/client";
import type { Role, User, CaseDecision, CaseStatus } from "@/domain/types";
import type { BackendThesis, CreateThesisRequest } from "@/types/backend";
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
  theses: BackendThesis[];
  activeThesisId: string | null;
  thesisLoading: boolean;
  thesisError: string | null;
};

const STORAGE_KEY = "vc-brain-demo-state-v1";

const defaultState: AppState = {
  user: { id: "u-analyst", name: "Jordan Lee", role: "ANALYST" },
  caseOverrides: {},
  theses: [],
  activeThesisId: null,
  thesisLoading: true,
  thesisError: null,
};

const AppContext = createContext<{
  state: AppState;
  activeThesis: BackendThesis | null;
  setRole: (role: Role) => void;
  setUserName: (name: string) => void;
  setCaseOverride: (caseId: string, patch: Partial<CaseOverride>) => void;
  recordDecision: (caseId: string, decision: CaseDecision) => void;
  setActiveThesis: (id: string | null) => void;
  refreshTheses: () => Promise<void>;
  createThesis: (req: CreateThesisRequest) => Promise<BackendThesis>;
  resetDemo: () => void;
} | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AppState>(() => loadState());

  useEffect(() => {
    saveState(state);
  }, [state]);

  const activeThesis = useMemo(
    () => state.theses.find((t) => t.id === state.activeThesisId) || null,
    [state.theses, state.activeThesisId]
  );

  const refreshTheses = useCallback(async () => {
    setState((prev) => ({ ...prev, thesisLoading: true, thesisError: null }));
    try {
      const theses = await api.theses.list();
      setState((prev) => {
        const stillActive = theses.some((t) => t.id === prev.activeThesisId);
        return {
          ...prev,
          theses,
          activeThesisId: stillActive ? prev.activeThesisId : (theses[0]?.id ?? null),
          thesisLoading: false,
          thesisError: null,
        };
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load thesis";
      setState((prev) => ({ ...prev, thesisLoading: false, thesisError: message }));
    }
  }, []);

  useEffect(() => {
    refreshTheses();
  }, [refreshTheses]);

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

  const setActiveThesis = useCallback((id: string | null) => {
    setState((prev) => ({ ...prev, activeThesisId: id }));
  }, []);

  const createThesis = useCallback(async (req: CreateThesisRequest) => {
    const created = await api.theses.create(req);
    setState((prev) => ({
      ...prev,
      theses: [created, ...prev.theses],
      activeThesisId: created.id,
    }));
    return created;
  }, []);

  const resetDemo = useCallback(() => {
    setState(defaultState);
    refreshTheses();
  }, [refreshTheses]);

  return (
    <AppContext.Provider
      value={{
        state,
        activeThesis,
        setRole,
        setUserName,
        setCaseOverride,
        recordDecision,
        setActiveThesis,
        refreshTheses,
        createThesis,
        resetDemo,
      }}
    >
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
