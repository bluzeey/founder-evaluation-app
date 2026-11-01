import { invalidateAll } from "@/api/cache";

export const AUTH_EXPIRED_EVENT = "founderos:auth-expired";
export const GOOGLE_LOGIN_URL = "/api/auth/login";

export type OwnerSession = {
  authenticated: true;
  email: string;
  user_id: number;
  workspace_mode: "shared" | "private";
};

export function clearPrivateClientState(): void {
  invalidateAll();
  // Earlier releases persisted the whole thesis list. Keep private records on
  // the authenticated server and in the mounted workspace only.
  try {
    localStorage.removeItem("vc-brain-demo-state-v2");
  } catch {
    // Storage can be disabled by browser privacy settings.
  }
}

export async function checkOwnerSession(signal?: AbortSignal): Promise<OwnerSession | null> {
  const response = await fetch("/api/auth/me", {
    credentials: "same-origin",
    cache: "no-store",
    signal,
  });
  if (response.status === 401) {
    clearPrivateClientState();
    return null;
  }
  if (!response.ok || !response.headers.get("content-type")?.includes("application/json")) {
    throw new Error("Sign-in is temporarily unavailable. Please retry.");
  }
  const session: unknown = await response.json();
  if (
    !session || typeof session !== "object" ||
    !("authenticated" in session) || session.authenticated !== true ||
    !("email" in session) || typeof session.email !== "string" || !session.email ||
    !("user_id" in session) || typeof session.user_id !== "number" ||
    !Number.isSafeInteger(session.user_id) || session.user_id < 1 ||
    !("workspace_mode" in session) || !["shared", "private"].includes(String(session.workspace_mode))
  ) {
    throw new Error("Your sign-in could not be verified. Please retry.");
  }
  return session as OwnerSession;
}

export async function signOutOwner(): Promise<void> {
  const response = await fetch("/api/auth/logout", {
    method: "POST",
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!response.ok && response.status !== 401) {
    throw new Error("Could not sign out. Please retry.");
  }
  clearPrivateClientState();
  window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
}
