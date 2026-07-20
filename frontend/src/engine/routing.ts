import type { CaseStatus, DriverAssessment, DriverKey, InvestmentCase, TriggeredRule } from "@/domain/types";
import { SPIKE_RULES, ROUTING_CONFIDENCE_FLOOR } from "@/config/weights";

export type AssociateScreenScores = {
  founderScore: number | null;
  visionProductScore: number | null;
  differentiationScore: number | null;
  tractionScore: number | null;
};

export function evaluateAssociateRecommendation(scores: AssociateScreenScores): {
  recommended: boolean;
  trigger:
    | "ONE_SCORE_GT_75_AND_TWO_SCORES_GT_50"
    | "ONE_SCORE_GT_75"
    | "TWO_SCORES_GT_50"
    | "NOT_RECOMMENDED"
    | "INCOMPLETE_EVALUATION";
} {
  const values = Object.values(scores);
  if (values.some((value) => value === null)) {
    return { recommended: false, trigger: "INCOMPLETE_EVALUATION" };
  }

  const numeric = values as number[];
  const oneHigh = numeric.some((value) => value > 75);
  const twoAbove50 = numeric.filter((value) => value > 50).length >= 2;

  if (oneHigh && twoAbove50) {
    return { recommended: true, trigger: "ONE_SCORE_GT_75_AND_TWO_SCORES_GT_50" };
  }
  if (oneHigh) {
    return { recommended: true, trigger: "ONE_SCORE_GT_75" };
  }
  if (twoAbove50) {
    return { recommended: true, trigger: "TWO_SCORES_GT_50" };
  }
  return { recommended: false, trigger: "NOT_RECOMMENDED" };
}

export function detectSpike(drivers: DriverAssessment[]): TriggeredRule[] {
  const triggered: TriggeredRule[] = [];

  // Valuation/cap structure cannot create a positive spike.
  const spikeableDrivers = drivers.filter((d) => d.key !== "VALUATION_CAP");

  const highSpike = spikeableDrivers.find(
    (d) => d.score >= SPIKE_RULES.ONE_DRIVER_HIGH.minScore && d.confidence >= SPIKE_RULES.ONE_DRIVER_HIGH.minConfidence
  );
  if (highSpike) {
    triggered.push({
      rule: "ONE_HIGH_SPIKE",
      driver: highSpike.key,
      score: highSpike.score,
      confidence: highSpike.confidence,
    });
  }

  const qualifying = spikeableDrivers.filter(
    (d) => d.score >= SPIKE_RULES.TWO_DRIVERS_QUALIFYING.minScore && d.confidence >= SPIKE_RULES.TWO_DRIVERS_QUALIFYING.minConfidence
  );
  if (qualifying.length >= 2) {
    for (const d of qualifying) {
      if (!triggered.find((t) => t.driver === d.key && t.rule === "ONE_HIGH_SPIKE")) {
        triggered.push({
          rule: "TWO_QUALIFYING_SPIKES",
          driver: d.key,
          score: d.score,
          confidence: d.confidence,
        });
      }
    }
  }

  return triggered;
}

export function routeCase(investmentCase: InvestmentCase): CaseStatus {
  // 1. Material unresolved contradiction -> VALIDATION_HOLD
  if (investmentCase.validationHoldReason || hasMaterialContradiction(investmentCase)) {
    return "VALIDATION_HOLD";
  }

  // 2. Thesis INELIGIBLE -> DECLINED or MONITORING
  if (investmentCase.thesisResult === "INELIGIBLE") {
    return "DECLINED";
  }
  if (investmentCase.thesisResult === "EXCEPTION_REVIEW") {
    return "SCREENING";
  }

  // 3. Any decision-critical confidence below 0.45 -> DILIGENCE
  if (decisionCriticalConfidenceLow(investmentCase)) {
    return "DILIGENCE";
  }

  // 4. Spike rule satisfied -> ASSOCIATE_REVIEW
  const spikes = detectSpike(investmentCase.drivers);
  if (spikes.length > 0) {
    return "ASSOCIATE_REVIEW";
  }

  // 5. Associate recommendation completed -> PARTNER_REVIEW
  if (investmentCase.status === "ASSOCIATE_REVIEW") {
    // In a real workflow this would be an explicit handoff. Demo default keeps it stable.
    return "ASSOCIATE_REVIEW";
  }

  // 6. Otherwise -> SCREENING or DILIGENCE
  if (decisionCriticalConfidenceLow(investmentCase, 0.55)) return "DILIGENCE";
  return investmentCase.status === "DISCOVERED" ? "SCREENING" : investmentCase.status || "SCREENING";
}

export function hasMaterialContradiction(investmentCase: InvestmentCase): boolean {
  return investmentCase.claims.some((c) => c.status === "CONTRADICTED" && c.contradictionPenalty >= 0.5);
}

export function decisionCriticalConfidenceLow(investmentCase: InvestmentCase, floor = ROUTING_CONFIDENCE_FLOOR): boolean {
  const criticalKeys: DriverKey[] = ["FOUNDER", "MARKET", "VISION_PRODUCT"];
  return investmentCase.drivers
    .filter((d) => criticalKeys.includes(d.key))
    .some((d) => d.confidence < floor);
}

export function nextStatusAfterDecision(
  decision: "INVEST" | "DECLINE" | "MONITOR" | "REQUEST_EVIDENCE",
  current: CaseStatus
): CaseStatus {
  switch (decision) {
    case "INVEST":
      return "INVESTED";
    case "DECLINE":
      return "DECLINED";
    case "MONITOR":
      return "MONITORING";
    case "REQUEST_EVIDENCE":
      return "DILIGENCE";
    default:
      return current;
  }
}

export function allowedTransitions(status: CaseStatus): CaseStatus[] {
  switch (status) {
    case "VALIDATION_HOLD":
      return ["VALIDATION_HOLD", "DILIGENCE", "DECLINED"];
    case "ASSOCIATE_REVIEW":
      return ["ASSOCIATE_REVIEW", "PARTNER_REVIEW", "DILIGENCE", "DECLINED"];
    case "PARTNER_REVIEW":
      return ["PARTNER_REVIEW", "INVESTED", "DECLINED", "MONITORING", "DILIGENCE"];
    case "DILIGENCE":
      return ["DILIGENCE", "ASSOCIATE_REVIEW", "SCREENING", "DECLINED"];
    case "SCREENING":
      return ["SCREENING", "DILIGENCE", "ASSOCIATE_REVIEW", "DECLINED"];
    default:
      return ["SCREENING", "DILIGENCE", "ASSOCIATE_REVIEW", "DECLINED"];
  }
}
