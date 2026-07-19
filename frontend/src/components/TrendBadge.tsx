import type { Trend } from "@/domain/types";

const trendIcon: Record<Trend, string> = {
  IMPROVING: "↑",
  DECLINING: "↓",
  STABLE: "→",
  INSUFFICIENT_HISTORY: "?",
};

const trendColor: Record<Trend, string> = {
  IMPROVING: "text-verified bg-verified/10 border-verified/20",
  DECLINING: "text-contradiction bg-contradiction/10 border-contradiction/20",
  STABLE: "text-concrete bg-concrete/10 border-concrete/20",
  INSUFFICIENT_HISTORY: "text-uncertain bg-uncertain/10 border-uncertain/20",
};

export function TrendBadge({ trend }: { trend: Trend }) {
  return (
    <span className={`rounded-sm border px-2 py-0.5 text-[10px] font-mono font-semibold tabular ${trendColor[trend]}`}>
      {trendIcon[trend]} {trend.replace(/_/g, " ")}
    </span>
  );
}

export default TrendBadge;
