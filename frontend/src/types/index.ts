export interface DimensionBreakdown {
  dimension: string;
  weight: number;
  raw_score: number;
  adjusted_score: number;
  confidence: number;
  evidence_band_low: number;
  evidence_band_high: number;
  coverage: number;
  evidence_count: number;
  contradiction_count: number;
  unknown: boolean;
  positive_evidence: string[];
  counter_evidence: string[];
  unknowns: string[];
  next_test?: string;
}

export interface ScoreSnapshot {
  id: string;
  founder_id: string;
  rubric_version: string;
  prompt_version: string;
  model_version: string;
  created_at: string;
  founder_score: number;
  evidence_band_low: number;
  evidence_band_high: number;
  overall_confidence: number;
  evidence_coverage: number;
  trend: number;
  dimension_breakdowns: DimensionBreakdown[];
  evidence_items: EvidenceItem[];
  change_explanation?: string;
}

export interface EvidenceItem {
  id: string;
  founder_id: string;
  dimension: string;
  observation: string;
  source_type: string;
  source_id: string;
  source_locator: string;
  evidence_type: string;
  rubric_level: number;
  source_trust: number;
  task_relevance: number;
  recency_factor: number;
  independence_group: string;
  polarity: string;
  status: string;
  counter_evidence?: string;
  unknowns?: string;
  created_at: string;
}

export interface Founder {
  id: string;
  name: string;
  email: string;
  current_company?: string;
  role?: string;
  location?: string;
  linkedin_url?: string;
  github_url?: string;
  ai_research_summary?: string;
  ai_research_sources?: string[];
  latest_score_snapshot?: ScoreSnapshot;
}

export interface ResearchFounderRequest {
  query: string;
  channels?: string[];
  auto_score?: boolean;
}

export interface Thesis {
  id: string;
  name: string;
  sectors: string[];
  stages: string[];
  geographies: string[];
  check_size_min: number;
  check_size_max: number;
  risk_appetite: string;
}

export interface OpportunityScreen {
  opportunity_id: string;
  founder_id: string;
  founder_score: number;
  founder_confidence: number;
  founder_market_fit: {
    score?: number;
    confidence: number;
    coverage: number;
  };
  team_completeness: {
    score?: number;
    confidence: number;
    coverage: number;
  };
  market_posture: string;
  market_confidence: number;
  idea_vs_market_posture: string;
  idea_vs_market_confidence: number;
  next_founder_action?: string;
}

export interface Claim {
  id: string;
  opportunity_id: string;
  claim: string;
  source: string;
  trust_status: string;
  confidence: number;
  contradiction?: string;
  owner?: string;
  next_action?: string;
}

export type AssessmentModule =
  | "problem_framing"
  | "sales_objection"
  | "prioritization"
  | "belief_updating"
  | "scaling_leadership"
  | "setback_ownership"
  | "claim_calibration"
  | "role_work_sample";

export interface AssessmentPlan {
  founder_id: string;
  recommended_modules: AssessmentModule[];
  reason: string;
}

export type Decision = "advance" | "diligence" | "hold" | "decline";
