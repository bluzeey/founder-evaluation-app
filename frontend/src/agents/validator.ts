import type { AgentContext, ValidationOutput } from "./contracts";

export function validator(ctx: AgentContext): ValidationOutput {
  const { investmentCase } = ctx;
  const accepted = investmentCase.claims
    .filter((c) => c.status === "VERIFIED" || c.status === "DECLARED")
    .map((c) => c.id);
  const downgraded: ValidationOutput["downgradedClaims"] = [];
  const quarantined: ValidationOutput["quarantinedClaims"] = [];

  for (const c of investmentCase.claims) {
    if (c.status === "CONTRADICTED") {
      quarantined.push({
        claimId: c.id,
        reason: `Contradicted by another source. Trust score reduced to ${c.trustScore}.`,
      });
    } else if (c.claimKind === "PROJECTION" || c.claimKind === "ASSUMPTION") {
      downgraded.push({
        claimId: c.id,
        reason: "Projection or assumption requires corroboration before use in scoring.",
        newTrustScore: Math.round(c.trustScore * 0.8 * 100) / 100,
      });
    }
  }

  const material = quarantined.length > 0 && Boolean(investmentCase.validationHoldReason);
  return {
    acceptedClaimIds: accepted,
    downgradedClaims: downgraded,
    quarantinedClaims: quarantined,
    materialContradiction: material,
    holdReason: investmentCase.validationHoldReason,
  };
}

export default validator;
