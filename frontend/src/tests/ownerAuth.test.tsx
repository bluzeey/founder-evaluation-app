import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { OwnerAuthGate } from "@/auth/OwnerAuthGate";
import { AUTH_EXPIRED_EVENT, checkOwnerSession, signOutOwner } from "@/auth/session";
import { __cacheInternals, cacheGet, invalidateAll } from "@/api/cache";
import { api } from "@/api/client";

const jsonResponse = (value: unknown, status = 200) => new Response(JSON.stringify(value), {
  status, headers: { "Content-Type": "application/json" },
});

beforeEach(() => {
  vi.restoreAllMocks();
  invalidateAll();
  vi.stubGlobal("localStorage", { removeItem: vi.fn() });
  vi.stubGlobal("window", Object.assign(new EventTarget(), { location: { search: "" } }));
});

describe("private owner session", () => {
  it("does not render private workspace children before verifying sign-in", () => {
    const html = renderToString(<OwnerAuthGate><div>PRIVATE-RECORD-FIXTURE</div></OwnerAuthGate>);
    expect(html).toContain("Checking your sign-in");
    expect(html).not.toContain("PRIVATE-RECORD-FIXTURE");
  });

  it("uses a same-origin uncached cookie request without a browser access key", async () => {
    const user = { authenticated: true, email: "person@example.test", user_id: 2, workspace_mode: "private" };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(user));
    vi.stubGlobal("fetch", fetchMock);
    await expect(checkOwnerSession()).resolves.toEqual(user);
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/me", expect.objectContaining({ credentials: "same-origin", cache: "no-store" }));
    expect(fetchMock.mock.calls[0][1]).not.toHaveProperty("headers");
  });

  it("clears cached data and legacy persisted records when the session is missing", async () => {
    await cacheGet(async () => ({ private: "fixture" }), "/v1/theses");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "Sign in required" }, 401)));
    await expect(checkOwnerSession()).resolves.toBeNull();
    expect(__cacheInternals.size()).toBe(0);
    expect(localStorage.removeItem).toHaveBeenCalledWith("vc-brain-demo-state-v2");
  });

  it("fails closed on an unavailable or malformed sign-in response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ authenticated: true })));
    await expect(checkOwnerSession()).rejects.toThrow("could not be verified");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>Unavailable</html>", { headers: { "Content-Type": "text/html" } })));
    await expect(checkOwnerSession()).rejects.toThrow("temporarily unavailable");
  });

  it("revokes sign-in through POST and clears the mounted workspace", async () => {
    const onExpired = vi.fn();
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await signOutOwner();
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/logout", expect.objectContaining({ method: "POST", credentials: "same-origin" }));
    expect(onExpired).toHaveBeenCalledTimes(1);
  });

  it("does not pretend sign-out succeeded when revocation failed", async () => {
    const onExpired = vi.fn();
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, 503)));
    await expect(signOutOwner()).rejects.toThrow("Could not sign out");
    expect(onExpired).not.toHaveBeenCalled();
  });

  it("a protected API 401 clears private caches and hides the workspace", async () => {
    const onExpired = vi.fn();
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, 401)));
    await expect(api.founders.list()).rejects.toMatchObject({ status: 401 });
    expect(onExpired).toHaveBeenCalledTimes(1);
    expect(__cacheInternals.size()).toBe(0);
  });

  it("an older in-flight request cannot refill private caches after sign-out", async () => {
    let finish!: (value: unknown) => void;
    const pending = cacheGet(() => new Promise((resolve) => { finish = resolve; }), "/v1/theses");
    invalidateAll();
    finish({ private: "fixture" });
    await pending;
    expect(__cacheInternals.size()).toBe(0);
  });
});
