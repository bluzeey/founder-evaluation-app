export type BackendThesis = {
  id: string;
  name: string;
  sectors: string[];
  stages: string[];
  geographies: string[];
  check_size_min: number;
  check_size_max: number;
  risk_appetite: string;
  min_evidence_requirements: Record<string, unknown>;
  created_at: string;
};

export type BackendFounder = {
  id: string;
  name: string;
  email: string;
  current_company?: string;
  role?: string;
  location?: string;
  location_city?: string;
  linkedin_url?: string;
  github_url?: string;
  source_reason?: string;
  source_url?: string;
  ai_research_summary?: string;
  ai_research_sources: string[];
  social_background_id?: string;
  latest_score_snapshot?: BackendScoreSnapshot;
   enrichment_policy?: "AUTO" | "MANUAL" | "NONE";
  created_at?: string;
  updated_at?: string;
};

export type BackendRecommendationTrigger =
  | "ONE_SCORE_GT_75_AND_TWO_SCORES_GT_50"
  | "ONE_SCORE_GT_75"
  | "TWO_SCORES_GT_50"
  | "NOT_RECOMMENDED"
  | "INCOMPLETE_EVALUATION";

export type BackendScreeningFundingStatus =
  | "no_public_institutional_funding_found"
  | "non_dilutive_grant_or_prize_only"
  | "public_equity_funding_found"
  | "unknown";

export type BackendFounderScreeningProfile = {
  id: string;
  founder_id: string;
  external_record_id?: string;
  project_name?: string;
  project_summary?: string;
  founder_role?: string;
  sector?: string;
  stage?: string;
  source_type?: string;
  institution_or_program?: string;
  school_or_lab?: string;
  cohort_year?: string;
  institution_affiliation_basis?: string;
  city?: string;
  country?: string;
  city_basis?: string;
  city_confidence?: number;
  target_market_geography?: string;
  website_url?: string;
  primary_source_url?: string;
  source_locator?: string;
  source_date?: string;
  funding_status: BackendScreeningFundingStatus;
  funding_check_as_of?: string;
  funding_check_confidence?: number;
  funding_notes?: string;
  founder_score?: number;
  founder_score_rationale?: string;
  vision_product_score?: number;
  vision_product_rationale?: string;
  differentiation_score?: number;
  differentiation_rationale?: string;
  traction_score?: number;
  traction_rationale?: string;
  evidence_confidence?: number;
  evidence_coverage?: number;
  individual_attribution_confidence?: number;
  evaluation_scope?: string;
  key_evidence: string[];
  counter_evidence: string[];
  unknowns: string[];
  next_diligence_action?: string;
  recommended: boolean;
  recommendation_trigger: BackendRecommendationTrigger;
  recommended_reason?: string;
  evaluation_version: string;
  pedigree_used_in_scoring: boolean;
  import_status?: string;
  research_priority?: string;
  tags: string[];
  imported_associate_call_recommended?: boolean;
  imported_recommendation_trigger?: string;
  imported_recommended_reason?: string;
  produced_by?: string;
  import_id?: string;
  created_at: string;
  updated_at: string;
};

export type BackendFounderDiscoveryFacets = {
  cities: string[];
  institutions_or_programs: string[];
  schools_or_labs: string[];
  source_types: string[];
  sectors: string[];
  funding_statuses: string[];
  cohort_years: string[];
};

export type BackendFounderDiscoveryItem = {
  founder: BackendFounder;
  profile?: BackendFounderScreeningProfile | null;
  opportunity?: BackendOpportunity | null;
};

export type BackendFounderDiscoveryPage = {
  items: BackendFounderDiscoveryItem[];
  total: number;
  limit: number;
  offset: number;
  facets: BackendFounderDiscoveryFacets;
};

export type BackendCsvImportRowError = {
  row_number: number;
  external_record_id?: string;
  field?: string;
  message: string;
};

export type BackendCsvImportResult = {
  dry_run: boolean;
  file_name: string;
  rows_received: number;
  rows_valid: number;
  rows_invalid: number;
  founders_to_create: number;
  founders_to_update: number;
  profiles_to_create: number;
  profiles_to_update: number;
  rows_skipped: number;
  errors: BackendCsvImportRowError[];
  warnings: string[];
  import_id?: string;
  created_founder_ids: string[];
  updated_founder_ids: string[];
  created_profile_ids: string[];
  updated_profile_ids: string[];
};

export type BackendScoreSnapshot = {
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
  dimension_breakdowns: BackendDimensionBreakdown[];
  evidence_items: BackendEvidenceItem[];
  change_explanation?: string;
};

export type BackendDimensionBreakdown = {
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
};

export type BackendEvidenceItem = {
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
  created_at?: string;
};

export type BackendOpportunity = {
  opportunity_id: string;
  founder_id: string;
  founder_score: number;
  founder_confidence: number;
  founder_market_fit: {
    domain_knowledge?: number;
    customer_access?: number;
    unique_insight?: number;
    personal_motivation?: number;
    problem_proximity?: number;
    technical_operational_advantage?: number;
    score?: number;
    confidence: number;
    coverage: number;
  };
  team_completeness: {
    complementary_skills?: number;
    missing_critical_roles?: string[];
    co_founder_alignment?: number;
    decision_rights?: number;
    commitment_availability?: number;
    score?: number;
    confidence: number;
    coverage: number;
  };
  market_posture: string;
  market_confidence: number;
  idea_vs_market_posture: string;
  idea_vs_market_confidence: number;
  next_founder_action?: string;
  status: string;
};

export type BackendClaim = {
  id: string;
  opportunity_id: string;
  founder_id?: string;
  claim: string;
  source: string;
  trust_status: string;
  confidence: number;
  contradiction?: string;
  owner?: string;
  next_action?: string;
};

export type PoolItemStatus = "recommended" | "approved" | "dismissed";

export type BackendPoolItem = {
  id: string;
  name: string;
  email?: string;
  current_company?: string;
  role?: string;
  location?: string;
  linkedin_url?: string;
  github_url?: string;
  source_url?: string;
  source?: string;
  reason: string;
  thesis_id?: string;
  job_id?: string;
  status: PoolItemStatus;
  created_at: string;
};

export type ApprovedPoolItemResponse = {
  founder: BackendFounder;
  opportunity_id: string;
};

export type SourceConfig = {
  platform: string;
  keywords: string;
};

export type BackendSourcingSchedule = {
  id: string;
  thesis_id: string;
  enabled: boolean;
  interval_seconds: number;
  max_leads_per_run: number;
  sources: SourceConfig[];
  last_run_at?: string;
  next_run_at?: string;
  created_at: string;
  updated_at: string;
};

export type BackendSourcingJob = {
  id: string;
  thesis_id: string;
  schedule_id?: string;
  status: string;
  progress: number;
  started_at?: string;
  ended_at?: string;
  leads_found: number;
  leads_added: number;
  leads_skipped: number;
  result?: Record<string, unknown>;
  error_message?: string;
  created_at: string;
};

export type BackendSourcingStatus = {
  schedules: BackendSourcingSchedule[];
  active_jobs: BackendSourcingJob[];
  recent_jobs: BackendSourcingJob[];
  last_dispatch_at?: string;
};

export type BackendEnrichmentRun = {
  id: string;
  founder_id: string;
  stage: string;
  status: string;
  evidence_added: number;
  confidence_before?: number;
  confidence_after?: number;
  started_at?: string;
  ended_at?: string;
  error_message?: string;
  created_at: string;
};

export type BackendEnrichmentStatus = {
  below_threshold_count: number;
  confidence_threshold: number;
  last_dispatch_at?: string;
  recent_runs: BackendEnrichmentRun[];
};

export type BackendSeedResponse = {
  thesis_id: string;
  founder_id: string;
  opportunity_id: string;
  message: string;
};

export type CreateSourcingScheduleRequest = {
  thesis_id: string;
  enabled?: boolean;
  interval_seconds?: number;
  max_leads_per_run?: number;
  sources?: SourceConfig[];
};

export type UpdateSourcingScheduleRequest = {
  enabled?: boolean;
  interval_seconds?: number;
  max_leads_per_run?: number;
  sources?: SourceConfig[];
};

export type CreateThesisRequest = {
  name: string;
  sectors?: string[];
  stages?: string[];
  geographies?: string[];
  check_size_min?: number;
  check_size_max?: number;
  risk_appetite?: string;
  min_evidence_requirements?: Record<string, unknown>;
};

export type UpdateThesisRequest = {
  name?: string;
  sectors?: string[];
  stages?: string[];
  geographies?: string[];
  check_size_min?: number;
  check_size_max?: number;
  risk_appetite?: string;
  min_evidence_requirements?: Record<string, unknown>;
};

export type CreateFounderRequest = {
  name: string;
  email: string;
  current_company?: string;
  role?: string;
  location?: string;
  linkedin_url?: string;
  github_url?: string;
  enrichment_policy?: "AUTO" | "MANUAL" | "NONE";
};

export type UploadDeckResponse = {
  opportunity_id: string;
  founder_id?: string;
  task_id: string;
  status: string;
};

export type QueuedResponse = {
  task_id?: string;
  job_id?: string;
  status: string;
  [key: string]: unknown;
};

export type ApiError = {
  status: number;
  message: string;
};

export function isBackendOpportunity(candidate: unknown): candidate is BackendOpportunity {
  return (
    typeof candidate === "object" &&
    candidate !== null &&
    "opportunity_id" in candidate &&
    typeof (candidate as Record<string, unknown>).opportunity_id === "string" &&
    "founder_id" in candidate
  );
}

export function isBackendPoolItem(candidate: unknown): candidate is BackendPoolItem {
  return (
    typeof candidate === "object" &&
    candidate !== null &&
    "id" in candidate &&
    typeof (candidate as Record<string, unknown>).id === "string" &&
    "name" in candidate
  );
}

export function isBackendFounder(candidate: unknown): candidate is BackendFounder {
  return (
    typeof candidate === "object" &&
    candidate !== null &&
    "id" in candidate &&
    typeof (candidate as Record<string, unknown>).id === "string" &&
    "name" in candidate
  );
}
