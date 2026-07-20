import type {
  BackendCsvImportResult,
  BackendFounderDiscoveryPage,
  BackendFounderScreeningProfile,
  BackendThesis,
  BackendFounder,
  BackendOpportunity,
  BackendClaim,
  BackendPoolItem,
  BackendSourcingSchedule,
  BackendSourcingJob,
  BackendSourcingStatus,
  BackendSeedResponse,
  BackendScoreSnapshot,
  BackendEnrichmentRun,
  BackendEnrichmentStatus,
  CreateSourcingScheduleRequest,
  UpdateSourcingScheduleRequest,
  CreateThesisRequest,
  UpdateThesisRequest,
  CreateFounderRequest,
  UploadDeckResponse,
  QueuedResponse,
  ApiError,
  ApprovedPoolItemResponse,
} from "@/types/backend";
import { cacheGet, invalidate, invalidateAll } from "@/api/cache";

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) || "/api";

// Re-export cache invalidation helpers so callers (e.g. DealRoom) can
// force a fresh read after a backend-side state change.
export const invalidateCache = invalidate;
export const invalidateAllCache = invalidateAll;

async function handleResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get("content-type") || "";
  const isHtml = contentType.includes("text/html");
  if (!response.ok || isHtml) {
    let message: string;
    if (isHtml) {
      message = "Backend returned HTML instead of JSON. Check that the backend is running and VITE_API_URL is set correctly.";
    } else {
      message = `Request failed with status ${response.status}`;
      try {
        const body = (await response.json()) as { detail?: string };
        if (body.detail) message = body.detail;
      } catch {
        // ignore body parse error
      }
    }
    throw { status: response.status, message } as ApiError;
  }
  return (await response.json()) as T;
}

async function get<T>(path: string): Promise<T> {
  return cacheGet(async () => {
    const response = await fetch(`${API_BASE}${path}`);
    return handleResponse<T>(response);
  }, path);
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(response);
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse<T>(response);
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse<T>(response);
}

async function del<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { method: "DELETE" });
  return handleResponse<T>(response);
}

async function postForm<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: formData,
  });
  return handleResponse<T>(response);
}

function withQuery(path: string, params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

export const api = {
  seed: () =>
    post<BackendSeedResponse>("/v1/seed").then((r) => {
      invalidateAll();
      return r;
    }),
  seedAll: () =>
    post<{
      theses_created: string[];
      schedules_created: string[];
      founders_created: string[];
      opportunities_created: string[];
      pool_items_created: string[];
      message: string;
    }>("/v1/seed/all").then((r) => {
      invalidateAll();
      return r;
    }),

  theses: {
    list: () => get<BackendThesis[]>("/v1/theses"),
    get: (id: string) => get<BackendThesis>(`/v1/theses/${id}`),
    create: (req: CreateThesisRequest) =>
      post<BackendThesis>("/v1/theses", req).then((r) => {
        invalidate("/v1/theses");
        return r;
      }),
    update: (id: string, req: UpdateThesisRequest) =>
      put<BackendThesis>(`/v1/theses/${id}`, req).then((r) => {
        invalidate(`/v1/theses/${id}`);
        invalidate("/v1/theses");
        return r;
      }),
  },

  founders: {
    list: () => get<BackendFounder[]>("/v1/founders"),
    get: (id: string) => get<BackendFounder>(`/v1/founders/${id}`),
    discovery: (params: Record<string, string | number | boolean | null | undefined> = {}) =>
      get<BackendFounderDiscoveryPage>(withQuery("/v1/founders/discovery", params)),
    recommended: (params: Record<string, string | number | boolean | null | undefined> = {}) =>
      get<BackendFounderDiscoveryPage>(withQuery("/v1/founders/recommended", params)),
    screeningProfile: (id: string) =>
      get<BackendFounderScreeningProfile>(`/v1/founders/${id}/screening-profile`),
    updateScreeningProfile: (id: string, req: Partial<BackendFounderScreeningProfile>) =>
      put<BackendFounderScreeningProfile>(`/v1/founders/${id}/screening-profile`, req).then((r) => {
        invalidate(`/v1/founders/${id}/screening-profile`);
        invalidate("/v1/founders/discovery");
        invalidate("/v1/founders/recommended");
        invalidate("/v1/founders");
        invalidate("/v1/opportunities");
        return r;
      }),
    importCsv: (file: File, opts: { dryRun?: boolean; force?: boolean } = {}) => {
      const formData = new FormData();
      formData.append("file", file);
      return postForm<BackendCsvImportResult>(
        withQuery("/v1/founders/import-csv", {
          dry_run: opts.dryRun ?? true,
          force: opts.force ?? false,
        }),
        formData
      ).then((r) => {
        if (!r.dry_run) {
          invalidate("/v1/founders/discovery");
          invalidate("/v1/founders/recommended");
          invalidate("/v1/founders");
          invalidate("/v1/opportunities");
        }
        return r;
      });
    },
    score: (id: string) => get<BackendScoreSnapshot>(`/v1/founders/${id}/score`),
    estimate: (id: string) =>
      post<QueuedResponse>(`/v1/founders/${id}/estimate`).then((r) => {
        invalidate(`/v1/founders/${id}/score`);
        invalidate("/v1/enrichment/runs");
        return r;
      }),
    enrich: (id: string) =>
      post<QueuedResponse>(`/v1/founders/${id}/enrich`).then((r) => {
        invalidate(`/v1/founders/${id}/score`);
        invalidate("/v1/enrichment/runs");
        return r;
      }),
    create: (req: CreateFounderRequest) =>
      post<BackendFounder>("/v1/founders", req).then((r) => {
        invalidate("/v1/founders");
        invalidate("/v1/founders/discovery");
        invalidate("/v1/founders/recommended");
        return r;
      }),
  },

  enrichment: {
    runs: (founderId?: string) =>
      get<BackendEnrichmentRun[]>(
        `/v1/enrichment/runs${founderId ? `?founder_id=${encodeURIComponent(founderId)}` : ""}`
      ),
    status: () => get<BackendEnrichmentStatus>("/v1/enrichment/status"),
  },

  pool: {
    list: (status?: string) =>
      get<BackendPoolItem[]>(`/v1/founders/pool${status ? `?status=${status}` : ""}`),
    approve: (id: string) =>
      post<ApprovedPoolItemResponse>(`/v1/founders/pool/${id}/approve`).then((r) => {
        invalidate("/v1/founders/pool");
        return r;
      }),
    dismiss: (id: string) =>
      post<BackendPoolItem>(`/v1/founders/pool/${id}/dismiss`).then((r) => {
        invalidate("/v1/founders/pool");
        return r;
      }),
    refresh: (thesisId?: string) =>
      post<QueuedResponse>(`/v1/founders/pool/refresh${thesisId ? `?thesis_id=${thesisId}` : ""}`).then((r) => {
        invalidate("/v1/founders/pool");
        return r;
      }),
  },

  opportunities: {
    list: (status?: string) =>
      get<BackendOpportunity[]>(`/v1/opportunities${status ? `?status=${encodeURIComponent(status)}` : ""}`),
    get: (id: string) => get<BackendOpportunity>(`/v1/opportunities/${id}`),
    screen: (id: string, founderId?: string) =>
      post<BackendOpportunity>(
        `/v1/opportunities/${id}/screen${founderId ? `?founder_id=${encodeURIComponent(founderId)}` : ""}`
      ).then((r) => {
        invalidate("/v1/opportunities");
        return r;
      }),
    updateStatus: (id: string, status: string) =>
      patch<BackendOpportunity>(`/v1/opportunities/${id}/status`, { status }).then((r) => {
        invalidate(`/v1/opportunities/${id}`);
        invalidate("/v1/opportunities");
        return r;
      }),
    diligence: (id: string) => get<BackendClaim[]>(`/v1/opportunities/${id}/diligence`),
    uploadDeck: (id: string, file: File, founderId?: string) => {
      const formData = new FormData();
      formData.append("file", file);
      const query = founderId ? `?founder_id=${encodeURIComponent(founderId)}` : "";
      return postForm<UploadDeckResponse>(`/v1/opportunities/${id}/deck${query}`, formData).then((r) => {
        invalidate(`/v1/opportunities/${id}`);
        return r;
      });
    },
  },

  sourcing: {
    status: () => get<BackendSourcingStatus>("/v1/sourcing/status"),
    schedules: () => get<BackendSourcingSchedule[]>("/v1/sourcing/schedules"),
    createSchedule: (req: CreateSourcingScheduleRequest) =>
      post<BackendSourcingSchedule>("/v1/sourcing/schedules", req).then((r) => {
        invalidate("/v1/sourcing/schedules");
        return r;
      }),
    updateSchedule: (id: string, req: UpdateSourcingScheduleRequest) =>
      put<BackendSourcingSchedule>(`/v1/sourcing/schedules/${id}`, req).then((r) => {
        invalidate("/v1/sourcing/schedules");
        return r;
      }),
    deleteSchedule: (id: string) =>
      del<{ id: string; deleted: boolean }>(`/v1/sourcing/schedules/${id}`).then((r) => {
        invalidate("/v1/sourcing/schedules");
        return r;
      }),
    jobs: () => get<BackendSourcingJob[]>("/v1/sourcing/jobs"),
    runNow: (thesisId: string) =>
      post<QueuedResponse>(`/v1/theses/${thesisId}/source-now`).then((r) => {
        invalidate("/v1/sourcing/status");
        invalidate("/v1/sourcing/jobs");
        return r;
      }),
  },
};

export default api;
