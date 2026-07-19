import type { AgentContext, SpecialistOutput } from "./contracts";

export function founderAnalyst(ctx: AgentContext): SpecialistOutput {
  const d = ctx.investmentCase.drivers.find((x) => x.key === "FOUNDER");
  if (!d) {
    return {
      driver: "FOUNDER",
      recommendedScore: 50,
      confidence: 0.3,
      rubricReason: "No founder evidence available.",
      supportingClaimIds: [],
      opposingClaimIds: [],
      missingEvidence: ["Founder track record", "Reference checks", "Public artifacts"],
    };
  }
  return {
    driver: "FOUNDER",
    recommendedScore: d.score,
    confidence: d.confidence,
    rubricReason: d.rubricReason,
    supportingClaimIds: d.supportingClaimIds,
    opposingClaimIds: d.opposingClaimIds,
    missingEvidence: d.missingEvidence,
    recommendedNextQuestion: "Can you walk us through a hard scaling decision you owned?",
  };
}

export default founderAnalyst;
