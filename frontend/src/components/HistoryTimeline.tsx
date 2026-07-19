import type { EvidenceEvent } from "@/domain/types";

export function HistoryTimeline({ events }: { events?: EvidenceEvent[] }) {
  if (!events || events.length === 0) return (
    <div className="panel text-sm text-slate-500">No history events yet.</div>
  );
  return (
    <div className="panel space-y-4">
      {events.map((e) => (
        <div key={e.id} className="relative border-l-2 border-slate-200 pl-4">
          <div className="absolute -left-[5px] top-1 h-2 w-2 rounded-full bg-action" />
          <div className="text-xs font-semibold text-ink">{e.eventType.replace(/_/g, " ")}</div>
          <div className="text-[10px] text-slate-500">
            {new Date(e.effectiveAt).toLocaleString()} · Affected: {e.affectedDrivers.join(", ")}
          </div>
          <p className="mt-1 text-sm text-slate-700">{e.explanation}</p>
          {Object.keys(e.previousValues).length > 0 && (
            <div className="mt-2 text-xs text-slate-600">
              {Object.entries(e.previousValues).map(([key, prev]) => {
                const next = e.newValues[key as keyof typeof e.newValues];
                return (
                  <div key={key}>
                    {key}: {prev} → {next}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default HistoryTimeline;
