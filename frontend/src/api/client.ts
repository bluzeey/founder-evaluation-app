import type {
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
  CreateSourcingScheduleRequest,
  UpdateSourcingScheduleRequest,
  CreateFounderRequest,
  UploadDeckResponse,
  QueuedResponse,
  ApiError,
} from "@/types/backend";

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) || "/api";

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
  const response = await fetch(`${API_BASE}${path}`);
  return handleResponse<T>(response);
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

export const api = {
  seed: () => post<BackendSeedResponse>("/v1/seed"),

  theses: {
    list: () => get<BackendThesis[]>("/v1/theses"),
  },

  founders: {
    list: () => get<BackendFounder[]>("/v1/founders"),
    get: (id: string) => get<BackendFounder>(`/v1/founders/${id}`),
    score: (id: string) => get<BackendScoreSnapshot>(`/v1/founders/${id}/score`),
    create: (req: CreateFounderRequest) => post<BackendFounder>("/v1/founders", req),
  },

  pool: {
    list: (status?: string) =>
      get<BackendPoolItem[]>(`/v1/founders/pool${status ? `?status=${status}` : ""}`),
    approve: (id: string) => post<BackendFounder>(`/v1/founders/pool/${id}/approve`),
    dismiss: (id: string) => post<BackendPoolItem>(`/v1/founders/pool/${id}/dismiss`),
    refresh: (thesisId?: string) =>
      post<QueuedResponse>(`/v1/founders/pool/refresh${thesisId ? `?thesis_id=${thesisId}` : ""}`),
  },

  opportunities: {
    list: () => get<BackendOpportunity[]>("/v1/opportunities"),
    get: (id: string) => get<BackendOpportunity>(`/v1/opportunities/${id}`),
    screen: (id: string, founderId?: string) =>
      post<BackendOpportunity>(
        `/v1/opportunities/${id}/screen${founderId ? `?founder_id=${encodeURIComponent(founderId)}` : ""}`
      ),
    diligence: (id: string) => get<BackendClaim[]>(`/v1/opportunities/${id}/diligence`),
    uploadDeck: (id: string, file: File, founderId?: string) => {
      const formData = new FormData();
      formData.append("file", file);
      const query = founderId ? `?founder_id=${encodeURIComponent(founderId)}` : "";
      return postForm<UploadDeckResponse>(`/v1/opportunities/${id}/deck${query}`, formData);
    },
  },

  sourcing: {
    status: () => get<BackendSourcingStatus>("/v1/sourcing/status"),
    schedules: () => get<BackendSourcingSchedule[]>("/v1/sourcing/schedules"),
    createSchedule: (req: CreateSourcingScheduleRequest) =>
      post<BackendSourcingSchedule>("/v1/sourcing/schedules", req),
    updateSchedule: (id: string, req: UpdateSourcingScheduleRequest) =>
      put<BackendSourcingSchedule>(`/v1/sourcing/schedules/${id}`, req),
    deleteSchedule: (id: string) => del<{ id: string; deleted: boolean }>(`/v1/sourcing/schedules/${id}`),
    jobs: () => get<BackendSourcingJob[]>("/v1/sourcing/jobs"),
    runNow: (thesisId: string) => post<QueuedResponse>(`/v1/theses/${thesisId}/source-now`),
  },
};

export default api;
