import type { ThesisConfig } from "@/domain/types";

export const DEFAULT_CHECK_SIZE = 100_000;
export const DEFAULT_OWNERSHIP_TARGET = 0.05; // 5%
export const DEFAULT_DECISION_SLA_HOURS = 24;

export const DEFAULT_THESIS: ThesisConfig = {
  sector: ["Artificial Intelligence", "AI Infrastructure", "AI Software"],
  stage: ["pre-seed"],
  geography: ["United States", "Germany"],
  checkSize: DEFAULT_CHECK_SIZE,
  ownershipTarget: DEFAULT_OWNERSHIP_TARGET,
  riskAppetite: "MODERATE",
  exclusions: [
    "No direct-to-consumer social apps",
    "No crypto or Web3 tokens",
    "No regulated medical diagnostics",
    "No prior institutional funding rounds",
  ],
};

export const THESIS_DESCRIPTION =
  "Technical founder, AI infrastructure, pre-seed, no prior institutional funding, recent shipped artifact, United States or Germany.";

export const ONE_DECISION_PER_DAYS = 5; // operational cadence target

export function isWithinThesis(companySector: string, stage: string, geography: string, thesis: ThesisConfig): {
  eligible: boolean;
  matches: string[];
  mismatches: string[];
} {
  const matches: string[] = [];
  const mismatches: string[] = [];

  const sectorMatch = thesis.sector.some(
    (s) => s.toLowerCase() === companySector.toLowerCase() || companySector.toLowerCase().includes(s.toLowerCase())
  );
  if (sectorMatch) matches.push("sector");
  else mismatches.push(`sector: ${companySector}`);

  const stageMatch = thesis.stage.some((s) => stage.toLowerCase().includes(s.toLowerCase()));
  if (stageMatch) matches.push("stage");
  else mismatches.push(`stage: ${stage}`);

  const geoMatch = thesis.geography.some(
    (g) => g.toLowerCase() === geography.toLowerCase() || geography.toLowerCase().includes(g.toLowerCase())
  );
  if (geoMatch) matches.push("geography");
  else mismatches.push(`geography: ${geography}`);

  return { eligible: sectorMatch && stageMatch && geoMatch, matches, mismatches };
}

export function parseThesisQuery(query: string): Partial<ThesisConfig> & { parsed: boolean; keywords: string[] } {
  const keywords = query.toLowerCase().split(/[\s,]+/).filter(Boolean);
  const parsed: Partial<ThesisConfig> & { parsed: boolean; keywords: string[] } = {
    parsed: true,
    keywords: Array.from(new Set(keywords)),
    sector: [],
    stage: [],
    geography: [],
    checkSize: DEFAULT_CHECK_SIZE,
    ownershipTarget: DEFAULT_OWNERSHIP_TARGET,
    riskAppetite: "MODERATE",
  };

  if (keywords.some((k) => k.includes("ai") || k.includes("artificial intelligence") || k.includes("infrastructure"))) {
    parsed.sector = ["Artificial Intelligence", "AI Infrastructure"];
  }
  if (keywords.some((k) => k.includes("pre-seed") || k.includes("preseed") || k.includes("seed"))) {
    parsed.stage = ["pre-seed"];
  }
  if (keywords.some((k) => k.includes("united states") || k.includes("us") || k.includes("germany") || k.includes("de"))) {
    parsed.geography = ["United States", "Germany"];
  }
  if (keywords.some((k) => k.includes("shipped") || k.includes("artifact") || k.includes("hackathon"))) {
    parsed.stage = ["pre-seed"];
  }
  if (keywords.some((k) => k.includes("funding"))) {
    // no-op: captured in stage
  }
  return parsed;
}
