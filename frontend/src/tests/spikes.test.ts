import { describe, it, expect } from "vitest";
import { routeCase, detectSpike } from "@/engine/routing";
import { caseB } from "@/data/demoCases";
import type { DriverAssessment, InvestmentCase } from "@/domain/types";

describe("spikes", () => {
  it("detects the seeded founder spike in case B", () => {
    const spikes = detectSpike(caseB.drivers);
    expect(spikes.some((s) => s.driver === "FOUNDER")).toBe(true);
  });

  it("routes case B to associate review because of the founder spike", () => {
    expect(routeCase(caseB)).toBe("ASSOCIATE_REVIEW");
  });

  it("does not allow valuation/cap to create a spike", () => {
    const spike = detectSpike(
      makeCaseWithScores({ FOUNDER: 50, MARKET: 50, VISION_PRODUCT: 50, TRACTION: 50, DIFFERENTIATION: 50, VALUATION_CAP: 95, confidence: 0.9 }).drivers
    );
    expect(spike.length).toBe(0);
  });
});

function makeCaseWithScores(
  opts: Partial<Record<DriverAssessment["key"], number>> & { confidence?: number }
): InvestmentCase {
  const base = caseB;
  const drivers = base.drivers.map((d) => ({
    ...d,
    score: opts[d.key] ?? d.score,
    confidence: opts.confidence ?? d.confidence,
  }));
  return { ...base, id: `spike-test-${JSON.stringify(opts)}`, drivers, claims: base.claims, validationHoldReason: undefined };
}
