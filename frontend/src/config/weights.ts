import type { DriverKey } from "@/domain/types";

export const DRIVER_WEIGHTS: Record<DriverKey, number> = {
  FOUNDER: 0.35,
  MARKET: 0.15,
  VISION_PRODUCT: 0.10,
  TRACTION: 0.10,
  DIFFERENTIATION: 0.20,
  VALUATION_CAP: 0.10,
};

export const DRIVER_LABELS: Record<DriverKey, string> = {
  FOUNDER: "Founder",
  MARKET: "Market",
  VISION_PRODUCT: "Vision and product",
  TRACTION: "Traction",
  DIFFERENTIATION: "Differentiation",
  VALUATION_CAP: "Valuation / Cap structure",
};

export const AXIS_LABELS: Record<"FOUNDER" | "MARKET" | "IDEA_MARKET", string> = {
  FOUNDER: "Founder",
  MARKET: "Market",
  IDEA_MARKET: "Idea vs. Market",
};

export const AXIS_DRIVERS: Record<"FOUNDER" | "MARKET" | "IDEA_MARKET", DriverKey[]> = {
  FOUNDER: ["FOUNDER"],
  MARKET: ["MARKET"],
  IDEA_MARKET: ["VISION_PRODUCT", "TRACTION", "DIFFERENTIATION", "VALUATION_CAP"],
};

export const CLAIM_TRUST_WEIGHTS = {
  sourceReliability: 0.30,
  extractionConfidence: 0.20,
  corroboration: 0.20,
  recency: 0.15,
  evidenceSpecificity: 0.15,
  contradictionPenalty: 0.35,
};

export const SPIKE_RULES = {
  ONE_DRIVER_HIGH: { minScore: 85, minConfidence: 0.70 },
  TWO_DRIVERS_QUALIFYING: { minScore: 75, minConfidence: 0.65 },
};

export const ROUTING_CONFIDENCE_FLOOR = 0.45;
