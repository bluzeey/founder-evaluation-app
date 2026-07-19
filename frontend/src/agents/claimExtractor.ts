import type { Claim, DeckExtractionResult, SourceRef } from "@/domain/types";

export function claimsFromDeck(caseId: string, deck: DeckExtractionResult, sourceRef?: Partial<SourceRef>): Claim[] {
  const now = new Date().toISOString();
  const claims: Claim[] = [];
  for (const slide of deck.slides) {
    for (const c of slide.claims) {
      const id = `${caseId}-deck-${slide.slide}-${claims.length + 1}`;
      const sRef: SourceRef = {
        id: `${caseId}-deck-${slide.slide}`,
        sourceType: "DECK",
        title: `Slide ${slide.slide}${slide.title ? `: ${slide.title}` : ""}`,
        slide: slide.slide,
        excerpt: slide.text,
        observedAt: now,
        ...sourceRef,
      };
      const reliability = c.claimKind === "FACT" ? 0.75 : c.claimKind === "PROJECTION" ? 0.55 : 0.6;
      const specificity = c.extractionConfidence >= 0.8 ? 0.8 : 0.5;
      const trustScore =
        0.3 * reliability +
        0.2 * c.extractionConfidence +
        0.2 * 0.2 +
        0.15 * 0.9 +
        0.15 * specificity;
      claims.push({
        id,
        caseId,
        category: c.category,
        text: c.text,
        status: c.claimKind === "FACT" ? "DECLARED" : "INFERRED",
        sourceRefs: [sRef],
        sourceReliability: reliability,
        extractionConfidence: c.extractionConfidence,
        corroboration: 0.2,
        recency: 0.9,
        evidenceSpecificity: specificity,
        contradictionPenalty: 0,
        trustScore: Math.round(trustScore * 100) / 100,
        claimKind: c.claimKind,
      });
    }
  }
  return claims;
}

export default claimsFromDeck;
