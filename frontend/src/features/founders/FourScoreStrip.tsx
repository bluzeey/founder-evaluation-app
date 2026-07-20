import type { BackendFounderScreeningProfile } from "@/types/backend";

type ScoreKey =
  | "founder_score"
  | "vision_product_score"
  | "differentiation_score"
  | "traction_score";

const SCORE_LABELS: Record<ScoreKey, string> = {
  founder_score: "Founder",
  vision_product_score: "Vision & Product",
  differentiation_score: "Differentiation",
  traction_score: "Traction",
};

function scoreTone(score: number | null | undefined) {
  if (score === null || score === undefined) {
    return {
      className: "border-concrete/30 bg-concrete/10 text-concrete",
      text: "Incomplete",
      value: "—",
    };
  }
  if (score > 75) {
    return {
      className: "border-verified/30 bg-verified/10 text-verified",
      text: "High trigger",
      value: String(score),
    };
  }
  if (score > 50) {
    return {
      className: "border-action/30 bg-action/10 text-action",
      text: "Qualifying",
      value: String(score),
    };
  }
  return {
    className: "border-concrete/30 bg-paper text-ink/80",
    text: "Does not qualify",
    value: String(score),
  };
}

export function FourScoreStrip({ profile }: { profile?: BackendFounderScreeningProfile | null }) {
  const entries: ScoreKey[] = [
    "founder_score",
    "vision_product_score",
    "differentiation_score",
    "traction_score",
  ];

  return (
    <div className="grid gap-1 sm:grid-cols-2 xl:grid-cols-4">
      {entries.map((key) => {
        const tone = scoreTone(profile?.[key]);
        return (
          <div
            key={key}
            className={`rounded-sm border px-2 py-1.5 text-xs ${tone.className}`}
            aria-label={`${SCORE_LABELS[key]} ${tone.value} ${tone.text}`}
            title={`${SCORE_LABELS[key]}: ${tone.value} (${tone.text})`}
          >
            <div className="font-medium text-[11px] uppercase tracking-wide">{SCORE_LABELS[key]}</div>
            <div className="mt-0.5 flex items-center justify-between gap-2">
              <span className="font-display text-sm font-bold tabular-nums">{tone.value}</span>
              <span className="text-[10px] uppercase tracking-wide">{tone.text}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function scoreValue(profile: BackendFounderScreeningProfile | null | undefined, key: ScoreKey) {
  const value = profile?.[key];
  return value === null || value === undefined ? "—" : String(value);
}
