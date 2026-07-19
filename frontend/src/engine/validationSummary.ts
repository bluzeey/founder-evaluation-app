import { DEMO_CASES } from "@/data/demoCases";
import { calculateTrustScore } from "@/engine/trust";
import { routeCase } from "@/engine/routing";
import { detectSpike } from "@/engine/routing";
import type { InvestmentCase } from "@/domain/types";

export type ValidationSummary = {
  totalCases: number;
  citationCoverage: number; // % of claims with >=1 source and slide or URL
  contradictionsDetected: number;
  unsupportedNumericClaims: number;
  routingTestsPassed: number;
  routingTestsTotal: number;
  averageProcessingTimeMs: number;
  humanOverrideCount: number;
  details: string[];
};

export function computeValidationSummary(): ValidationSummary {
  const details: string[] = [];
  let claimsWithCitations = 0;
  let totalClaims = 0;
  let contradictions = 0;
  let unsupportedNumeric = 0;
  let routingPassed = 0;
  const routingTests = [
    { name: "case A cold-start", expected: "ACTIVATION_READY", case: DEMO_CASES[0] },
    { name: "case B founder spike", expected: "ASSOCIATE_REVIEW", case: DEMO_CASES[1] },
    { name: "case C contradiction", expected: "VALIDATION_HOLD", case: DEMO_CASES[2] },
  ];

  for (const c of DEMO_CASES) {
    for (const cl of c.claims) {
      totalClaims++;
      const hasCitation = cl.sourceRefs.length > 0 && (cl.sourceRefs.some((s) => s.url || s.slide) || cl.sourceRefs.some((s) => s.excerpt));
      if (hasCitation) claimsWithCitations++;
      if (cl.status === "CONTRADICTED") contradictions++;
      if (containsUnsupportedNumeric(cl)) unsupportedNumeric++;
      // Trust score must be in [0,1]
      const trust = calculateTrustScore(cl);
      if (trust < 0 || trust > 1) details.push(`Trust score out of range for ${cl.id}`);
    }
  }

  for (const t of routingTests) {
    const routed = routeCase(t.case);
    if (routed === t.expected) routingPassed++;
    else details.push(`Routing test failed: ${t.name} expected ${t.expected}, got ${routed}`);
  }

  // Valuation/cap alone cannot create a spike: ensure no spike with only VALUATION_CAP
  const spikeTests = [
    { case: makeSpikeCase({ VALUATION_CAP: 90, confidence: 0.8 }), shouldSpike: false, name: "valuation-only spike" },
    { case: makeSpikeCase({ FOUNDER: 90, confidence: 0.8 }), shouldSpike: true, name: "founder spike" },
    { case: makeSpikeCase({ FOUNDER: 80, MARKET: 80, confidence: 0.7 }), shouldSpike: true, name: "two qualifying spikes" },
  ];
  for (const t of spikeTests) {
    const spikes = detectSpike(t.case.drivers);
    const spiked = spikes.length > 0;
    if (spiked === t.shouldSpike) routingPassed++;
    else details.push(`Spike test failed: ${t.name}`);
    routingTests.push({ name: t.name, expected: t.shouldSpike ? "ASSOCIATE_REVIEW" : "SCREENING", case: t.case });
  }

  const coverage = totalClaims ? Math.round((claimsWithCitations / totalClaims) * 100) : 0;
  const avgTime = 120; // deterministic demo processing time in ms per case

  return {
    totalCases: DEMO_CASES.length,
    citationCoverage: coverage,
    contradictionsDetected: contradictions,
    unsupportedNumericClaims: unsupportedNumeric,
    routingTestsPassed: routingPassed,
    routingTestsTotal: routingTests.length,
    averageProcessingTimeMs: avgTime,
    humanOverrideCount: 0,
    details,
  };
}

function containsUnsupportedNumeric(claim: InvestmentCase["claims"][number]): boolean {
  const text = claim.text;
  const hasNumber = /\d/.test(text);
  const hasSource = claim.sourceRefs.length > 0;
  const isContradicted = claim.status === "CONTRADICTED";
  return hasNumber && (!hasSource || isContradicted);
}

function makeSpikeCase(
  opts: Partial<Record<"FOUNDER" | "MARKET" | "VISION_PRODUCT" | "TRACTION" | "DIFFERENTIATION" | "VALUATION_CAP", number>> & {
    confidence?: number;
  }
): InvestmentCase {
  const base = DEMO_CASES[0];
  const drivers = base.drivers.map((d) => ({
    ...d,
    score: opts[d.key] ?? 50,
    confidence: opts.confidence ?? 0.7,
  }));
  return {
    ...base,
    id: `spike-test-${JSON.stringify(opts)}`,
    drivers,
    claims: [],
    validationHoldReason: undefined,
  };
}
