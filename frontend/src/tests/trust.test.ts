import { describe, it, expect } from "vitest";
import { calculateTrustScore } from "@/engine/trust";
import { caseC } from "@/data/demoCases";

describe("trust score", () => {
  it("clamps between 0 and 1", () => {
    const maxClaim = caseC.claims.reduce((a, b) => (a.trustScore > b.trustScore ? a : b));
    const minClaim = caseC.claims.reduce((a, b) => (a.trustScore < b.trustScore ? a : b));
    expect(calculateTrustScore(maxClaim)).toBeLessThanOrEqual(1);
    expect(calculateTrustScore(minClaim)).toBeGreaterThanOrEqual(0);
  });

  it("reduces trust when a contradiction penalty is high", () => {
    const contradicted = caseC.claims.find((c) => c.status === "CONTRADICTED")!;
    const declared = caseC.claims.find((c) => c.status === "DECLARED" && c.contradictionPenalty === 0)!;
    expect(calculateTrustScore(contradicted)).toBeLessThan(calculateTrustScore(declared));
  });
});
