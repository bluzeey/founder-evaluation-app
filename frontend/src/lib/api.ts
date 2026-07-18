import type { Founder, Thesis, ScoreSnapshot, OpportunityScreen, Claim, AssessmentPlan, AssessmentModule, ResearchFounderRequest } from "@/types";

const API_BASE = import.meta.env.VITE_API_URL || "/api";

async function fetcher<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  seed: () => fetcher<{ founder_id: string; opportunity_id: string; thesis_id: string }>("/v1/seed", { method: "POST" }),
  listFounders: () => fetcher<Founder[]>("/v1/founders"),
  getFounder: (id: string) => fetcher<Founder>(`/v1/founders/${id}`),
  getScore: (id: string) => fetcher<ScoreSnapshot>(`/v1/founders/${id}/score`),
  planAssessment: (id: string) => fetcher<AssessmentPlan>(`/v1/assessments/plan?founder_id=${id}`, { method: "POST" }),
  simulateAssessment: (founder_id: string, modules: AssessmentModule[], responses: Record<AssessmentModule, string>) =>
    fetcher<ScoreSnapshot>("/v1/assessments/simulate", {
      method: "POST",
      body: JSON.stringify({ founder_id, modules, responses }),
    }),
  screenOpportunity: (id: string) => fetcher<OpportunityScreen>(`/v1/opportunities/${id}/screen`, { method: "POST" }),
  getDiligence: (id: string) => fetcher<Claim[]>(`/v1/opportunities/${id}/diligence`),
  listTheses: () => fetcher<Thesis[]>("/v1/theses"),
  createThesis: (body: unknown) => fetcher<Thesis>("/v1/theses", { method: "POST", body: JSON.stringify(body) }),
  researchFounder: (body: ResearchFounderRequest) =>
    fetcher<Founder>("/v1/founders/research", { method: "POST", body: JSON.stringify(body) }),
};
