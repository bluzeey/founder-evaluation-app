import type { EvidenceEvent } from "@/domain/types";

export function HistoryTimeline({ events }: { events?: EvidenceEvent[] }) {
  if (!events || events.length === 0) return (
    <div className="panel text-sm text-concrete">No history events yet.</div>
  );
  return (
    <div className="panel space-y-4">
      {events.map((e) => (
        <div key={e.id} className="relative border-l-2 border-concrete/20 pl-4">
          <div className="absolute -left-[5px] top-1 h-2 w-2 rounded-full bg-action" />
          <div className="text-xs font-semibold text-ink">{e.eventType.replace(/_/g, " ")}</div>
          <div className="font-mono text-[10px] uppercase tracking-wide text-concrete">
            {new Date(e.effectiveAt).toLocaleString()} · Affected: {e.affectedDrivers.join(", ")}
          </div>
          <p className="mt-1 text-sm text-ink/80">{e.explanation}</p>
          {Object.keys(e.previousValues).length > 0 && (
            <div className="mt-2 font-mono text-xs text-concrete">
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
