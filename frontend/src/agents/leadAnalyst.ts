import type { AgentContext, LeadAnalystOutput } from "./contracts";

export function leadAnalyst(ctx: AgentContext): LeadAnalystOutput {
  const { investmentCase } = ctx;
  const assignments: LeadAnalystOutput["driverAssignments"] = {};
  for (const c of investmentCase.claims) {
    const key = categoryToDriver(c.category);
    const arr = assignments[key] || [];
    if (!arr.includes(c.id)) arr.push(c.id);
    assignments[key] = arr;
  }

  const nextQuestions = Array.from(
    new Set(investmentCase.drivers.flatMap((d) => d.missingEvidence).filter(Boolean))
  ).slice(0, 4);

  return {
    summary: `Lead analyst read ${investmentCase.claims.length} claims for ${investmentCase.id}. ` +
      `Top drivers: ${investmentCase.drivers
        .sort((a, b) => b.score - a.score)
        .slice(0, 2)
        .map((d) => `${d.key} (${d.score})`)
        .join(", ")}. ` +
      `Status: ${investmentCase.status}.`,
    driverAssignments: assignments,
    nextQuestions,
  };
}

function categoryToDriver(category: string): "FOUNDER" | "MARKET" | "VISION_PRODUCT" | "TRACTION" | "DIFFERENTIATION" | "VALUATION_CAP" {
  switch (category) {
    case "TEAM":
      return "FOUNDER";
    case "MARKET":
      return "MARKET";
    case "PRODUCT":
      return "VISION_PRODUCT";
    case "TRACTION":
      return "TRACTION";
    case "DIFFERENTIATION":
      return "DIFFERENTIATION";
    case "TERMS":
      return "VALUATION_CAP";
    default:
      return "VISION_PRODUCT";
  }
}

export default leadAnalyst;
