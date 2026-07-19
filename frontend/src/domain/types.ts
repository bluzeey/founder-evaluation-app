export type CaseStatus =
  | "DISCOVERED"
  | "ACTIVATION_READY"
  | "AWAITING_APPLICATION"
  | "SCREENING"
  | "DILIGENCE"
  | "VALIDATION_HOLD"
  | "ASSOCIATE_REVIEW"
  | "PARTNER_REVIEW"
  | "INVESTED"
  | "DECLINED"
  | "MONITORING";

export type ClaimStatus =
  | "DECLARED"
  | "INFERRED"
  | "VERIFIED"
  | "CONTRADICTED"
  | "UNRESOLVED";

export type Trend =
  | "IMPROVING"
  | "DECLINING"
  | "STABLE"
  | "INSUFFICIENT_HISTORY";

export type SourceType = "DECK" | "FORM" | "GITHUB" | "WEB" | "EVENT" | "REFERENCE";

export type SourceRef = {
  id: string;
  sourceType: SourceType;
  title: string;
  url?: string;
  slide?: number;
  excerpt?: string;
  observedAt: string;
};

export type ClaimCategory =
  | "TEAM"
  | "MARKET"
  | "PRODUCT"
  | "TRACTION"
  | "DIFFERENTIATION"
  | "TERMS";

export type Claim = {
  id: string;
  caseId: string;
  category: ClaimCategory;
  text: string;
  status: ClaimStatus;
  sourceRefs: SourceRef[];
  sourceReliability: number;
  extractionConfidence: number;
  corroboration: number;
  recency: number;
  evidenceSpecificity: number;
  contradictionPenalty: number;
  trustScore: number;
  claimKind?: "FACT" | "PROJECTION" | "ASSUMPTION" | "OPINION";
  contradictionOf?: string;
};

export type DriverKey =
  | "FOUNDER"
  | "MARKET"
  | "VISION_PRODUCT"
  | "TRACTION"
  | "DIFFERENTIATION"
  | "VALUATION_CAP";

export type DriverAssessment = {
  key: DriverKey;
  score: number;
  confidence: number;
  trend: Trend;
  supportingClaimIds: string[];
  opposingClaimIds: string[];
  missingEvidence: string[];
  rubricReason: string;
};

export type AxisKey = "FOUNDER" | "MARKET" | "IDEA_MARKET";

export type AxisAssessment = {
  key: AxisKey;
  score: number;
  confidence: number;
  trend: Trend;
  driverKeys: DriverKey[];
};

export type InvestmentCase = {
  id: string;
  companyId?: string;
  founderIds: string[];
  sourceChannel: string;
  inboundOrOutbound: "INBOUND" | "OUTBOUND";
  status: CaseStatus;
  thesisResult: "ELIGIBLE" | "EXCEPTION_REVIEW" | "INELIGIBLE";
  owner: string;
  createdAt: string;
  decisionDeadline: string;
  nextAction: string;
  claims: Claim[];
  drivers: DriverAssessment[];
  axes: AxisAssessment[];
  validationHoldReason?: string;
  triggeredRules: string[];
  memo?: CaseMemo;
  history?: EvidenceEvent[];
  skepticCounterCase?: string;
  strongestEvidenceClaimIds?: string[];
  termsCheckSize?: number;
  termsOwnershipTarget?: number;
  termsValuationCap?: number;
};

export type EvidenceEvent = {
  id: string;
  entityId: string;
  eventType: string;
  effectiveAt: string;
  observedAt: string;
  sourceRefIds: string[];
  affectedDrivers: DriverKey[];
  previousValues: Partial<Record<DriverKey, number>>;
  newValues: Partial<Record<DriverKey, number>>;
  explanation: string;
};

export type CaseMemo = {
  companySnapshot: string;
  hypotheses: string[];
  swot: { strengths: string[]; weaknesses: string[]; opportunities: string[]; threats: string[] };
  problemAndProduct: string;
  tractionKpis: string[];
  contradictions: string[];
  missingInformation: string[];
  recommendedNextAction: string;
  claimCitations: Record<string, string[]>;
};

export type DeckExtractionResult = {
  slides: Array<{
    slide: number;
    title?: string;
    text: string;
    claims: Array<{
      category: ClaimCategory;
      text: string;
      claimKind: "FACT" | "PROJECTION" | "ASSUMPTION" | "OPINION";
      extractionConfidence: number;
    }>;
  }>;
  missingSections: string[];
  unreadableSlides: number[];
};

export type SpecialistOutput = {
  driver: DriverKey;
  recommendedScore: number;
  confidence: number;
  rubricReason: string;
  supportingClaimIds: string[];
  opposingClaimIds: string[];
  missingEvidence: string[];
  recommendedNextQuestion?: string;
};

export type ValidationOutput = {
  acceptedClaimIds: string[];
  downgradedClaims: Array<{ claimId: string; reason: string; newTrustScore: number }>;
  quarantinedClaims: Array<{ claimId: string; reason: string }>;
  materialContradiction: boolean;
  holdReason?: string;
};

export type SkepticOutput = {
  strongestCounterCase: string;
  evidenceClaimIds: string[];
  decisionSensitiveUnknown: string;
  requestedReanalysis?: DriverKey;
};

export type TalentSignal = {
  id: string;
  person: string;
  currentProject?: string;
  artifactUrl?: string;
  sourceChannel: string;
  thesisTags: string[];
  strongestSignal: string;
  signalConfidence: number;
  signalDate: string;
  momentumTrend: Trend;
  status: CaseStatus;
  whyAppeared: string;
  caseId?: string;
};

export type Role = "ANALYST" | "ASSOCIATE" | "PARTNER";

export type DecisionOption = "INVEST" | "DECLINE" | "MONITOR" | "REQUEST_EVIDENCE";

export type CaseDecision = {
  caseId: string;
  role: Role;
  decision: DecisionOption;
  overrideReason?: string;
  requestedEvidence?: string;
  recordedAt: string;
};

export type User = {
  id: string;
  name: string;
  role: Role;
};

export type Duration = {
  totalSeconds: number;
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
  isExpired: boolean;
  percentRemaining: number;
};

export type ThesisConfig = {
  sector: string[];
  stage: string[];
  geography: string[];
  checkSize: number;
  ownershipTarget: number;
  riskAppetite: "CONSERVATIVE" | "MODERATE" | "AGGRESSIVE";
  exclusions: string[];
};

export type TriggeredRule = {
  rule: "ONE_HIGH_SPIKE" | "TWO_QUALIFYING_SPIKES";
  driver: DriverKey;
  score: number;
  confidence: number;
};
