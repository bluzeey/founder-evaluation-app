import type { Trend } from "@/domain/types";

const trendIcon: Record<Trend, string> = {
  IMPROVING: "↑",
  DECLINING: "↓",
  STABLE: "→",
  INSUFFICIENT_HISTORY: "?",
};

const trendColor: Record<Trend, string> = {
  IMPROVING: "text-verified bg-green-50",
  DECLINING: "text-contradiction bg-red-50",
  STABLE: "text-slate-600 bg-slate-100",
  INSUFFICIENT_HISTORY: "text-uncertain bg-amber-50",
};

export function TrendBadge({ trend }: { trend: Trend }) {
  return (
    <span className={`rounded px-2 py-0.5 text-[10px] font-semibold tabular ${trendColor[trend]}`}>
      {trendIcon[trend]} {trend.replace(/_/g, " ")}
    </span>
  );
}

export default TrendBadge;
