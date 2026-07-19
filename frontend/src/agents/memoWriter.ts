import type { AgentContext, MemoWriterOutput } from "./contracts";

export function memoWriter(ctx: AgentContext): MemoWriterOutput {
  const { investmentCase } = ctx;
  const memo = investmentCase.memo || {
    companySnapshot: "No memo available.",
    hypotheses: [],
    swot: { strengths: [], weaknesses: [], opportunities: [], threats: [] },
    problemAndProduct: "",
    tractionKpis: [],
    contradictions: [],
    missingInformation: [],
    recommendedNextAction: investmentCase.nextAction,
    claimCitations: {},
  };

  const lockedClaimIds = investmentCase.claims
    .filter((c) => c.status === "VERIFIED" || c.status === "INFERRED")
    .map((c) => c.id);

  return { memo, lockedClaimIds };
}

export default memoWriter;
