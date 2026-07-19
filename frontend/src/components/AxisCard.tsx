import type { AxisAssessment } from "@/domain/types";
import { AXIS_LABELS } from "@/config/weights";
import { TrendBadge } from "./TrendBadge";

export function AxisCard({ axis }: { axis: AxisAssessment }) {
  return (
    <div className={`index-card border-l-4 ${borderColor(axis.key)}`}>
      <div className="mb-2 flex items-center justify-between">
        <div className="label">Axis · {AXIS_LABELS[axis.key]}</div>
        <TrendBadge trend={axis.trend} />
      </div>
      <div className="flex items-baseline justify-between">
        <span className="font-display text-3xl font-bold tabular text-ink">{axis.score}</span>
        <span className="text-sm text-concrete">{Math.round(axis.confidence * 100)}% confidence</span>
      </div>
      <div className="mt-3 font-mono text-[10px] uppercase tracking-wide text-concrete">
        Drivers: {axis.driverKeys.join(", ")}
      </div>
    </div>
  );
}

function borderColor(key: AxisAssessment["key"]) {
  switch (key) {
    case "FOUNDER":
      return "border-l-action";
    case "MARKET":
      return "border-l-uncertain";
    case "IDEA_MARKET":
      return "border-l-contradiction";
    default:
      return "border-l-concrete";
  }
}

export default AxisCard;
