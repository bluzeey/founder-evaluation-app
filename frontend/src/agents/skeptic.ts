import type { AgentContext, SkepticOutput } from "./contracts";

export function skeptic(ctx: AgentContext): SkepticOutput {
  const { investmentCase } = ctx;
  const contradictory = investmentCase.claims.filter((c) => c.status === "CONTRADICTED");
  const weakest = investmentCase.drivers
    .filter((d) => d.confidence < 0.5)
    .sort((a, b) => a.confidence - b.confidence)[0];

  return {
    strongestCounterCase:
      investmentCase.skepticCounterCase ||
      (contradictory.length
        ? `The contradicted claims (${contradictory.map((c) => c.text).join("; ")}) suggest the most favorable evidence is unreliable.`
        : "The bull case relies on unverified founder-reported claims that have not been independently corroborated."),
    evidenceClaimIds: contradictory.map((c) => c.id),
    decisionSensitiveUnknown: weakest
      ? `${weakest.key} confidence is ${Math.round(weakest.confidence * 100)}%. Resolve before deciding.`
      : "What evidence could disprove the bull case?",
    requestedReanalysis: weakest?.key,
  };
}

export default skeptic;
