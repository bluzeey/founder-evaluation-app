import { describe, it, expect, beforeEach, vi } from "vitest";
import { cacheGet, invalidate, invalidateAll, __cacheInternals } from "@/api/cache";

beforeEach(() => {
  __cacheInternals.reset();
  vi.useFakeTimers();
});

describe("cacheGet", () => {
  it("fetches on miss and caches the result", async () => {
    const fetcher = vi.fn().mockResolvedValue({ hello: "world" });
    const result = await cacheGet(fetcher, "/v1/test");
    expect(result).toEqual({ hello: "world" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("returns cached data without fetching on a fresh hit", async () => {
    const fetcher = vi.fn().mockResolvedValue(42);
    await cacheGet(fetcher, "/v1/test");
    // immediate second call — within the default 5s fresh window
    const result = await cacheGet(fetcher, "/v1/test");
    expect(result).toBe(42);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("deduplicates concurrent in-flight requests", async () => {
    let resolve: (v: number) => void;
    const promise = new Promise<number>((r) => (resolve = r));
    const fetcher = vi.fn().mockReturnValue(promise);
    // two callers before the first fetch resolves
    const a = cacheGet(fetcher, "/v1/test");
    const b = cacheGet(fetcher, "/v1/test");
    resolve!(99);
    expect(await a).toBe(99);
    expect(await b).toBe(99);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("returns stale data immediately and refetches in the background", async () => {
    const fetcher = vi.fn();
    // first call populates the cache
    fetcher.mockResolvedValueOnce("v1");
    await cacheGet(fetcher, "/v1/test");

    // advance past the fresh window (5s) but within stale (30s)
    vi.advanceTimersByTime(6_000);

    // stale hit — returns old value, kicks background refetch
    fetcher.mockResolvedValueOnce("v2");
    const result = await cacheGet(fetcher, "/v1/test");
    expect(result).toBe("v1"); // stale

    // allow background refetch to complete
    await vi.runAllTimersAsync();
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("fetches fresh when the stale window has elapsed", async () => {
    const fetcher = vi.fn().mockResolvedValue("first");
    await cacheGet(fetcher, "/v1/test");

    // advance past both fresh (5s) and stale (30s) windows
    vi.advanceTimersByTime(31_000);

    fetcher.mockResolvedValueOnce("second");
    const result = await cacheGet(fetcher, "/v1/test");
    expect(result).toBe("second");
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("does not cache errors — a failed fetch lets the next call retry", async () => {
    const fetcher = vi.fn().mockRejectedValueOnce(new Error("boom"));
    await expect(cacheGet(fetcher, "/v1/test")).rejects.toThrow("boom");

    fetcher.mockResolvedValueOnce("ok");
    const result = await cacheGet(fetcher, "/v1/test");
    expect(result).toBe("ok");
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});

describe("invalidate", () => {
  it("removes entries whose key starts with the prefix", async () => {
    await cacheGet(vi.fn().mockResolvedValue("a"), "/v1/opportunities");
    await cacheGet(vi.fn().mockResolvedValue("b"), "/v1/opportunities/opp_1");
    await cacheGet(vi.fn().mockResolvedValue("c"), "/v1/founders");

    invalidate("/v1/opportunities");

    // both /v1/opportunities and /v1/opportunities/opp_1 are gone
    expect(__cacheInternals.size()).toBe(1);
  });

  it("does not touch entries outside the prefix", async () => {
    await cacheGet(vi.fn().mockResolvedValue("c"), "/v1/founders");
    invalidate("/v1/opportunities");
    expect(__cacheInternals.size()).toBe(1);
  });
});

describe("invalidateAll", () => {
  it("clears every entry", async () => {
    await cacheGet(vi.fn().mockResolvedValue("a"), "/v1/a");
    await cacheGet(vi.fn().mockResolvedValue("b"), "/v1/b");
    invalidateAll();
    expect(__cacheInternals.size()).toBe(0);
  });
});
