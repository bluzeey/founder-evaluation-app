import type { AgentContext, SpecialistOutput } from "./contracts";

export function marketAnalyst(ctx: AgentContext): SpecialistOutput {
  const d = ctx.investmentCase.drivers.find((x) => x.key === "MARKET");
  if (!d) {
    return {
      driver: "MARKET",
      recommendedScore: 50,
      confidence: 0.3,
      rubricReason: "No market evidence available.",
      supportingClaimIds: [],
      opposingClaimIds: [],
      missingEvidence: ["Buyer interviews", "Competitive map", "Market timing"],
    };
  }
  return {
    driver: "MARKET",
    recommendedScore: d.score,
    confidence: d.confidence,
    rubricReason: d.rubricReason,
    supportingClaimIds: d.supportingClaimIds,
    opposingClaimIds: d.opposingClaimIds,
    missingEvidence: d.missingEvidence,
    recommendedNextQuestion: "Who is the specific buyer and what budget line does this come from?",
  };
}

export default marketAnalyst;
