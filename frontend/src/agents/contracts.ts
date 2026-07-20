import type {
  Claim,
  DriverKey,
  InvestmentCase,
  SpecialistOutput,
  ValidationOutput,
  SkepticOutput,
  CaseMemo,
} from "@/domain/types";

export type { SpecialistOutput, ValidationOutput, SkepticOutput };

export interface AgentContext {
  investmentCase: InvestmentCase;
  claims: Claim[];
}

export interface LeadAnalystOutput {
  summary: string;
  driverAssignments: Partial<Record<DriverKey, string[]>>;
  nextQuestions: string[];
}

export interface DealCaptainOutput {
  owner: string;
  nextAction: string;
  recommendedStatus: InvestmentCase["status"];
  rationale: string;
}

export interface MemoWriterOutput {
  memo: CaseMemo;
  lockedClaimIds: string[];
}

export interface ExtractionAdapter {
  extractDeck: (deckName: string, deckText: string) => Promise<import("@/domain/types").DeckExtractionResult>;
}

export const AGENT_NAMES: Record<DriverKey, string> = {
  FOUNDER: "Founder Analyst",
  MARKET: "Market Analyst",
  VISION_PRODUCT: "Product Analyst",
  TRACTION: "Traction Analyst",
  DIFFERENTIATION: "Differentiation Analyst",
  VALUATION_CAP: "Terms Analyst",
};

export function specialistStub(
  driver: DriverKey,
  score: number,
  confidence: number,
  reason: string,
  supporting: string[],
  opposing: string[],
  missing: string[],
  nextQuestion?: string
): SpecialistOutput {
  return {
    driver,
    recommendedScore: score,
    confidence,
    rubricReason: reason,
    supportingClaimIds: supporting,
    opposingClaimIds: opposing,
    missingEvidence: missing,
    recommendedNextQuestion: nextQuestion,
  };
}

export function validationStub(
  accepted: string[],
  downgraded: ValidationOutput["downgradedClaims"],
  quarantined: ValidationOutput["quarantinedClaims"],
  material: boolean,
  holdReason?: string
): ValidationOutput {
  return {
    acceptedClaimIds: accepted,
    downgradedClaims: downgraded,
    quarantinedClaims: quarantined,
    materialContradiction: material,
    holdReason,
  };
}

export function skepticStub(counter: string, evidence: string[], unknown: string, reanalysis?: DriverKey): SkepticOutput {
  return {
    strongestCounterCase: counter,
    evidenceClaimIds: evidence,
    decisionSensitiveUnknown: unknown,
    requestedReanalysis: reanalysis,
  };
}
