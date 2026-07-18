import { TrendingUp, TrendingDown, Minus, HelpCircle } from "lucide-react";
import type { ScoreSnapshot } from "@/types";

interface Props {
  snapshot: ScoreSnapshot;
  size?: "sm" | "md" | "lg";
}

export default function ScoreCapsule({ snapshot, size = "md" }: Props) {
  const score = snapshot.founder_score;
  const low = snapshot.evidence_band_low;
  const high = snapshot.evidence_band_high;
  const confidence = Math.round(snapshot.overall_confidence * 100);
  const coverage = Math.round(snapshot.evidence_coverage * 100);

  const TrendIcon = snapshot.trend > 0 ? TrendingUp : snapshot.trend < 0 ? TrendingDown : Minus;
  const trendColor = snapshot.trend > 0 ? "text-verified" : snapshot.trend < 0 ? "text-contradiction" : "text-slate-400";

  const sizeClasses = {
    sm: "p-3",
    md: "p-5",
    lg: "p-6",
  };

  return (
    <div className={`panel ${sizeClasses[size]} flex flex-col gap-3`}>
      <div className="flex items-end justify-between">
        <div>
          <div className="label">Founder Score</div>
          <div className="flex items-baseline gap-3">
            <span className="text-5xl font-bold tabular text-ink">{score}</span>
            <span className={`flex items-center gap-1 text-sm font-medium ${trendColor}`}>
              <TrendIcon size={16} />
              {snapshot.trend > 0 ? `+${snapshot.trend}` : snapshot.trend === 0 ? "0" : snapshot.trend}
            </span>
          </div>
        </div>
        <div className="text-right">
          <div className="label">Evidence band</div>
          <div className="text-lg font-semibold tabular text-ink">
            {low}–{high}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-lg bg-slate-50 p-3">
          <div className="flex items-center gap-1.5 text-slate-500">
            <HelpCircle size={14} />
            Confidence
          </div>
          <div className="text-xl font-semibold tabular text-ink">{confidence}%</div>
        </div>
        <div className="rounded-lg bg-slate-50 p-3">
          <div className="label">Coverage</div>
          <div className="text-xl font-semibold tabular text-ink">{coverage}%</div>
        </div>
      </div>

      <p className="text-xs text-slate-500">
        {confidence < 45
          ? "There are promising signals, but additional evidence is required."
          : "Evidence-weighted estimate of persistent founder capability."}
      </p>
    </div>
  );
}
