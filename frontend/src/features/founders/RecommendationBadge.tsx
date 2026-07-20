import type { BackendRecommendationTrigger } from "@/types/backend";

const LABELS: Record<BackendRecommendationTrigger, string> = {
  ONE_SCORE_GT_75_AND_TWO_SCORES_GT_50: ">75 and two >50",
  ONE_SCORE_GT_75: "One >75",
  TWO_SCORES_GT_50: "Two >50",
  NOT_RECOMMENDED: "Not recommended",
  INCOMPLETE_EVALUATION: "Incomplete",
};

const STYLES: Record<BackendRecommendationTrigger, string> = {
  ONE_SCORE_GT_75_AND_TWO_SCORES_GT_50: "border-verified/30 bg-verified/10 text-verified",
  ONE_SCORE_GT_75: "border-verified/30 bg-verified/10 text-verified",
  TWO_SCORES_GT_50: "border-action/30 bg-action/10 text-action",
  NOT_RECOMMENDED: "border-concrete/30 bg-paper text-ink/80",
  INCOMPLETE_EVALUATION: "border-concrete/30 bg-concrete/10 text-concrete",
};

export function RecommendationBadge({ trigger }: { trigger?: BackendRecommendationTrigger | null }) {
  const value = trigger ?? "INCOMPLETE_EVALUATION";
  return (
    <span className={`inline-flex rounded-sm border px-2 py-1 text-xs font-medium ${STYLES[value]}`}>
      {LABELS[value]}
    </span>
  );
}

export function recommendationTriggerLabel(trigger?: BackendRecommendationTrigger | null) {
  return LABELS[trigger ?? "INCOMPLETE_EVALUATION"];
}
