import type { AgentContext, SpecialistOutput } from "./contracts";

export function productTractionAnalyst(ctx: AgentContext): SpecialistOutput {
  const vision = ctx.investmentCase.drivers.find((x) => x.key === "VISION_PRODUCT");
  const traction = ctx.investmentCase.drivers.find((x) => x.key === "TRACTION");

  const score = vision && traction ? Math.round((vision.score + traction.score) / 2) : 50;
  const confidence = vision && traction ? Math.min(vision.confidence, traction.confidence) : 0.3;
  const supporting = Array.from(new Set([...(vision?.supportingClaimIds || []), ...(traction?.supportingClaimIds || [])]));
  const opposing = Array.from(new Set([...(vision?.opposingClaimIds || []), ...(traction?.opposingClaimIds || [])]));
  const missing = Array.from(new Set([...(vision?.missingEvidence || []), ...(traction?.missingEvidence || [])]));

  return {
    driver: "VISION_PRODUCT",
    recommendedScore: score,
    confidence,
    rubricReason:
      vision && traction
        ? `Vision/Product: ${vision.rubricReason} | Traction: ${traction.rubricReason}`
        : "Product and traction evidence are sparse.",
    supportingClaimIds: supporting,
    opposingClaimIds: opposing,
    missingEvidence: missing,
    recommendedNextQuestion: "What is the smallest paying customer segment and how many repeat uses have you observed?",
  };
}

export default productTractionAnalyst;
