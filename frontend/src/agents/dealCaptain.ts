import type { AgentContext, DealCaptainOutput } from "./contracts";
import { routeCase } from "@/engine/routing";

export function dealCaptain(ctx: AgentContext): DealCaptainOutput {
  const { investmentCase } = ctx;
  const recommended = routeCase(investmentCase);
  return {
    owner: investmentCase.owner,
    nextAction: investmentCase.nextAction,
    recommendedStatus: recommended,
    rationale: `Routing result is ${recommended}. Material contradictions: ${investmentCase.validationHoldReason ? "yes" : "no"}. ` +
      `Spike rules: ${investmentCase.triggeredRules.length ? investmentCase.triggeredRules.join("; ") : "none"}.`,
  };
}

export default dealCaptain;
