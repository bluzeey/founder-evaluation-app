import { describe, it, expect } from "vitest";
import { routeCase } from "@/engine/routing";
import { caseA } from "@/data/demoCases";
import type { DriverAssessment } from "@/domain/types";

describe("cold-start routing", () => {
  it("stays stable when prestige-only signal is injected", () => {
    const baseRoute = routeCase(caseA);
    const prestige = {
      ...caseA,
      id: "prestige-test",
      claims: [
        ...caseA.claims,
        {
          id: "prestige-claim",
          caseId: caseA.id,
          category: "TEAM" as const,
          text: "Top-tier university and employer brand.",
          status: "INFERRED" as const,
          sourceRefs: [],
          sourceReliability: 0.6,
          extractionConfidence: 0.6,
          corroboration: 0.2,
          recency: 0.5,
          evidenceSpecificity: 0.4,
          contradictionPenalty: 0,
          trustScore: 0.4,
        },
      ],
    };
    expect(routeCase(prestige)).toBe(baseRoute);
  });

  it("routes to diligence when a critical driver is missing evidence", () => {
    const missing = {
      ...caseA,
      id: "missing-critical",
      drivers: caseA.drivers.map((d) =>
        d.key === "VISION_PRODUCT" ? { ...d, score: 50, confidence: 0.3 } : d
      ) as DriverAssessment[],
    };
    expect(routeCase(missing)).toBe("DILIGENCE");
  });
});
