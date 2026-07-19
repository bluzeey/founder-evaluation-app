import type { Claim } from "@/domain/types";
import { CLAIM_TRUST_WEIGHTS } from "@/config/weights";

export function calculateTrustScore(claim: Claim): number {
  const raw =
    CLAIM_TRUST_WEIGHTS.sourceReliability * claim.sourceReliability +
    CLAIM_TRUST_WEIGHTS.extractionConfidence * claim.extractionConfidence +
    CLAIM_TRUST_WEIGHTS.corroboration * claim.corroboration +
    CLAIM_TRUST_WEIGHTS.recency * claim.recency +
    CLAIM_TRUST_WEIGHTS.evidenceSpecificity * claim.evidenceSpecificity -
    CLAIM_TRUST_WEIGHTS.contradictionPenalty * claim.contradictionPenalty;
  return clamp(raw, 0, 1);
}

export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

export function recomputeClaimTrust(claim: Claim): Claim {
  return { ...claim, trustScore: calculateTrustScore(claim) };
}
