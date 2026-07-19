import type { DeckExtractionResult } from "@/domain/types";
import { DECK_EXTRACTIONS } from "@/data/demoCases";

export async function extractDeck(deckName: string, _deckText?: string): Promise<DeckExtractionResult> {
  const normalized = deckName.toLowerCase().replace(/\s+/g, "-");
  for (const key of Object.keys(DECK_EXTRACTIONS)) {
    if (normalized.includes(key) || key.includes(normalized)) {
      return DECK_EXTRACTIONS[key];
    }
  }
  if (normalized.includes("traction") || normalized.includes("revenue")) {
    return DECK_EXTRACTIONS["case-contradictory-traction"];
  }
  if (normalized.includes("prompt") || normalized.includes("founder")) {
    return DECK_EXTRACTIONS["case-founder-spike"];
  }
  if (normalized.includes("hackathon") || normalized.includes("code") || normalized.includes("github")) {
    return DECK_EXTRACTIONS["case-cold-start"];
  }
  return fallbackDeck(deckName);
}

function fallbackDeck(deckName: string): DeckExtractionResult {
  return {
    slides: [
      {
        slide: 1,
        title: deckName,
        text: "Deck uploaded. No structured extraction model is available; this is a deterministic fixture fallback.",
        claims: [
          {
            category: "PRODUCT",
            text: "Deck uploaded; content not extracted by live model.",
            claimKind: "ASSUMPTION",
            extractionConfidence: 0.3,
          },
        ],
      },
    ],
    missingSections: ["Team", "Market", "Traction", "Terms"],
    unreadableSlides: [2, 3, 4, 5, 6, 7, 8, 9],
  };
}

export default extractDeck;
