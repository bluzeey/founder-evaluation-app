import type { DriverAssessment } from "@/domain/types";
import { DRIVER_LABELS } from "@/config/weights";

export function DriverMiniBars({ drivers }: { drivers: DriverAssessment[] }) {
  return (
    <div className="space-y-2">
      {drivers.map((d) => {
        const color = d.score >= 75 ? "bg-green-500" : d.score >= 55 ? "bg-blue-500" : d.score >= 45 ? "bg-amber-500" : "bg-red-500";
        return (
          <div key={d.key} className="flex items-center gap-3">
            <div className="w-32 text-xs font-medium text-slate-600 truncate">{DRIVER_LABELS[d.key]}</div>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-200">
              <div className={`h-full ${color}`} style={{ width: `${d.score}%` }} />
            </div>
            <div className="w-16 text-right text-xs font-semibold tabular text-ink">
              {d.score} <span className="text-slate-400">({Math.round(d.confidence * 100)}%)</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default DriverMiniBars;
