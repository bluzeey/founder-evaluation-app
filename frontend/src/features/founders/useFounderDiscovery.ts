import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "@/api/client";
import type { BackendFounderDiscoveryPage } from "@/types/backend";

type UseFounderDiscoveryOptions = {
  recommendedOnly?: boolean;
};

const DEFAULT_LIMIT = 50;

export function useFounderDiscovery({ recommendedOnly = false }: UseFounderDiscoveryOptions) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchInput, setSearchInput] = useState(searchParams.get("q") ?? "");
  const [page, setPage] = useState<BackendFounderDiscoveryPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSearchInput(searchParams.get("q") ?? "");
  }, [searchParams]);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      const next = new URLSearchParams(searchParams);
      if (searchInput.trim()) {
        next.set("q", searchInput.trim());
      } else {
        next.delete("q");
      }
      next.set("offset", "0");
      setSearchParams(next, { replace: true });
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [searchInput]);

  const params = useMemo(() => {
    const offset = Number(searchParams.get("offset") ?? "0");
    return {
      q: searchParams.get("q") ?? undefined,
      recommended: recommendedOnly ? true : searchParams.get("recommended") ?? undefined,
      city: searchParams.get("city") ?? undefined,
      institution_or_program: searchParams.get("institution_or_program") ?? undefined,
      school_or_lab: searchParams.get("school_or_lab") ?? undefined,
      source_type: searchParams.get("source_type") ?? undefined,
      sector: searchParams.get("sector") ?? undefined,
      funding_status: searchParams.get("funding_status") ?? undefined,
      cohort_year: searchParams.get("cohort_year") ?? undefined,
      limit: Number(searchParams.get("limit") ?? String(DEFAULT_LIMIT)),
      offset: Number.isFinite(offset) ? offset : 0,
      sort: recommendedOnly ? "recommended" : searchParams.get("sort") ?? undefined,
    };
  }, [recommendedOnly, searchParams]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const loader = recommendedOnly ? api.founders.recommended : api.founders.discovery;
    loader(params)
      .then((result) => {
        if (!cancelled) setPage(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load founders");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [recommendedOnly, params]);

  function updateParam(key: string, value: string | null) {
    const next = new URLSearchParams(searchParams);
    if (value && value.length > 0) {
      next.set(key, value);
    } else {
      next.delete(key);
    }
    next.set("offset", "0");
    setSearchParams(next);
  }

  function goToOffset(offset: number) {
    const next = new URLSearchParams(searchParams);
    next.set("offset", String(Math.max(0, offset)));
    setSearchParams(next);
  }

  return {
    page,
    loading,
    error,
    params,
    searchInput,
    setSearchInput,
    updateParam,
    goToOffset,
  };
}
