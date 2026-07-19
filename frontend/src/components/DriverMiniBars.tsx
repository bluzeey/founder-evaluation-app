import type { DriverAssessment } from "@/domain/types";
import { DRIVER_LABELS } from "@/config/weights";

export function DriverMiniBars({ drivers }: { drivers: DriverAssessment[] }) {
  return (
    <div className="space-y-2">
      {drivers.map((d) => {
        const color = d.score >= 75 ? "bg-verified" : d.score >= 55 ? "bg-action" : d.score >= 45 ? "bg-uncertain" : "bg-contradiction";
        return (
          <div key={d.key} className="flex items-center gap-3">
            <div className="w-32 text-xs font-sans font-medium text-concrete truncate">{DRIVER_LABELS[d.key]}</div>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-concrete/15">
              <div className={`h-full ${color}`} style={{ width: `${d.score}%` }} />
            </div>
            <div className="w-20 text-right font-mono text-xs font-semibold tabular text-ink">
              {d.score} <span className="text-concrete">({Math.round(d.confidence * 100)}%)</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default DriverMiniBars;
