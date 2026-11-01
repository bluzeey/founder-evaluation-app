import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import {
  AUTH_EXPIRED_EVENT,
  GOOGLE_LOGIN_URL,
  checkOwnerSession,
  clearPrivateClientState,
  signOutOwner,
  type OwnerSession,
} from "./session";

type AuthState =
  | { status: "checking" }
  | { status: "signed-out" }
  | { status: "error"; message: string }
  | { status: "authenticated"; session: OwnerSession };

const OwnerContext = createContext<OwnerSession | null>(null);

export function OwnerAuthGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "checking" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    clearPrivateClientState();
    let disposed = false;
    let controller: AbortController | undefined;
    let timeout: ReturnType<typeof setTimeout> | undefined;

    const verify = async () => {
      controller?.abort();
      clearTimeout(timeout);
      const current = new AbortController();
      controller = current;
      timeout = setTimeout(() => current.abort(), 15_000);
      try {
        const session = await checkOwnerSession(current.signal);
        if (!disposed && controller === current) {
          setState(session ? { status: "authenticated", session } : { status: "signed-out" });
        }
      } catch {
        if (!disposed && controller === current) {
          clearPrivateClientState();
          setState({ status: "error", message: "Sign-in is temporarily unavailable. Please retry." });
        }
      } finally {
        if (controller === current) clearTimeout(timeout);
      }
    };

    const signedOut = () => {
      controller?.abort();
      controller = undefined;
      clearPrivateClientState();
      setState({ status: "signed-out" });
    };
    void verify();
    window.addEventListener(AUTH_EXPIRED_EVENT, signedOut);
    window.addEventListener("focus", verify);
    return () => {
      disposed = true;
      controller?.abort();
      clearTimeout(timeout);
      window.removeEventListener(AUTH_EXPIRED_EVENT, signedOut);
      window.removeEventListener("focus", verify);
    };
  }, [attempt]);

  if (state.status === "authenticated") {
    return <OwnerContext.Provider value={state.session}>{children}</OwnerContext.Provider>;
  }

  const accountRejected = typeof window !== "undefined" &&
    new URLSearchParams(window.location.search).has("auth_error");

  return (
    <main className="flex min-h-screen items-center justify-center bg-canvas px-6">
      <section className="w-full max-w-md rounded-lg border border-concrete/20 bg-paper p-8 shadow-paper">
        <p className="mb-3 text-xs font-mono uppercase tracking-widest text-concrete">Private workspace</p>
        <h1 className="font-display text-3xl font-bold text-ink">FounderOS</h1>
        {state.status === "checking" ? (
          <p className="mt-5 text-sm text-concrete" role="status">Checking your sign-in…</p>
        ) : (
          <>
            <p className="mt-4 text-sm text-concrete">Sign in with your approved Google account to open your workspace.</p>
            {(state.status === "error" || accountRejected) && (
              <p className="mt-4 text-sm text-red-700" role="alert">
                {state.status === "error" ? state.message : "That sign-in could not be completed. Use the Google account approved for this workspace."}
              </p>
            )}
            {state.status === "error" ? (
              <button className="mt-6 w-full rounded-md bg-action px-4 py-3 text-sm font-semibold text-paper" onClick={() => {
                setState({ status: "checking" });
                setAttempt((value) => value + 1);
              }}>Retry sign-in check</button>
            ) : (
              <a className="mt-6 block rounded-md bg-action px-4 py-3 text-center text-sm font-semibold text-paper" href={GOOGLE_LOGIN_URL}>Continue with Google</a>
            )}
          </>
        )}
      </section>
    </main>
  );
}

export function OwnerAccount() {
  const session = useContext(OwnerContext);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!session) return null;

  return (
    <div className="flex items-center gap-3 text-xs text-concrete">
      <span className="hidden sm:inline">{session.email}</span>
      <button disabled={busy} className="rounded border border-concrete/30 px-3 py-1.5 text-ink disabled:opacity-50" onClick={async () => {
        setBusy(true);
        setError("");
        try { await signOutOwner(); }
        catch { setError("Could not sign out. Please retry."); setBusy(false); }
      }}>{busy ? "Signing out…" : "Sign out"}</button>
      {error && <span role="alert">{error}</span>}
    </div>
  );
}
