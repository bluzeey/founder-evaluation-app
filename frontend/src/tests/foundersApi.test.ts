import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/api/client";
import { __cacheInternals, cacheGet } from "@/api/cache";

beforeEach(() => {
  __cacheInternals.reset();
  vi.restoreAllMocks();
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => "application/json" },
      json: async () => ({ items: [], total: 0, limit: 50, offset: 0, facets: { cities: [], institutions_or_programs: [], schools_or_labs: [], source_types: [], sectors: [], funding_statuses: [], cohort_years: [] } }),
    })
  );
});

describe("founder discovery api", () => {
  it("discovery uses URLSearchParams for filters", async () => {
    const fetchMock = vi.mocked(fetch);
    await api.founders.discovery({ city: "San Francisco", q: "Atlas", recommended: false });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/founders/discovery?")
    );
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("city=San+Francisco"));
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("q=Atlas"));
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("recommended=false"));
  });

  it("recommended always requests the recommended endpoint", async () => {
    const fetchMock = vi.mocked(fetch);
    await api.founders.recommended({ city: "Boston" });
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/api/v1/founders/recommended?city=Boston"));
  });

  it("screening profile update invalidates discovery and recommended caches", async () => {
    await cacheGet(async () => ({ ok: true }), "/v1/founders/discovery");
    await cacheGet(async () => ({ ok: true }), "/v1/founders/recommended");
    expect(__cacheInternals.size()).toBe(2);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        headers: { get: () => "application/json" },
        json: async () => ({ id: "fsp_1", founder_id: "fnd_1", funding_status: "unknown", key_evidence: [], counter_evidence: [], unknowns: [], recommended: false, recommendation_trigger: "INCOMPLETE_EVALUATION", evaluation_version: "associate_screen_v1", pedigree_used_in_scoring: false, tags: [], created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }),
      })
    );

    await api.founders.updateScreeningProfile("fnd_1", { founder_score: 80 } as never);
    expect(__cacheInternals.size()).toBe(0);
  });
});
