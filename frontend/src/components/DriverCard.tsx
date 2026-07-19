import type { DriverAssessment } from "@/domain/types";
import { DRIVER_LABELS } from "@/config/weights";
import { TrendBadge } from "./TrendBadge";

export function DriverCard({ driver, onClaimClick }: { driver: DriverAssessment; onClaimClick?: (id: string) => void }) {
  const supporting = driver.supportingClaimIds.slice(0, 2);
  const opposing = driver.opposingClaimIds.slice(0, 1);
  return (
    <div className="panel space-y-3">
      <div className="flex items-center justify-between">
        <div className="label">{DRIVER_LABELS[driver.key]}</div>
        <TrendBadge trend={driver.trend} />
      </div>
      <div className="flex items-baseline gap-3">
        <span className="text-3xl font-bold tabular text-ink">{driver.score}</span>
        <span className="text-sm text-slate-500">{Math.round(driver.confidence * 100)}% confidence</span>
      </div>
      <p className="text-sm text-slate-700">{driver.rubricReason}</p>
      <div className="space-y-2">
        {supporting.length > 0 && (
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wide text-verified">Supporting</div>
            <ul className="space-y-1">
              {supporting.map((id) => (
                <li key={id}>
                  <button
                    onClick={() => onClaimClick?.(id)}
                    className="text-left text-xs text-action hover:underline"
                  >
                    {id}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {opposing.length > 0 && (
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wide text-contradiction">Opposing</div>
            <ul className="space-y-1">
              {opposing.map((id) => (
                <li key={id}>
                  <button
                    onClick={() => onClaimClick?.(id)}
                    className="text-left text-xs text-contradiction hover:underline"
                  >
                    {id}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {driver.missingEvidence.length > 0 && (
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Missing</div>
            <ul className="space-y-1">
              {driver.missingEvidence.map((m) => (
                <li key={m} className="text-xs text-slate-600">
                  • {m}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

export default DriverCard;
