import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/lib/api";
import ScoreCapsule from "@/components/ScoreCapsule";
import EvidenceCard from "@/components/EvidenceCard";
import type { ScoreSnapshot } from "@/types";

export default function ScoreExplorer() {
  const { founderId } = useParams<{ founderId: string }>();
  const [snapshot, setSnapshot] = useState<ScoreSnapshot | null>(null);

  useEffect(() => {
    if (!founderId) return;
    api.getScore(founderId).then(setSnapshot);
  }, [founderId]);

  if (!snapshot) return <div className="panel py-12 text-center">Loading score explorer…</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-ink">Score evidence explorer</h1>
        <div className="text-xs text-slate-500">
          Rubric {snapshot.rubric_version} · Model {snapshot.model_version}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <ScoreCapsule snapshot={snapshot} />
        </div>

        <div className="panel lg:col-span-2">
          <h3 className="mb-4 text-lg font-semibold text-ink">Dimension calculation</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">Dimension</th>
                  <th className="px-3 py-2">Raw</th>
                  <th className="px-3 py-2">Adjusted</th>
                  <th className="px-3 py-2">Confidence</th>
                  <th className="px-3 py-2">Coverage</th>
                  <th className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {snapshot.dimension_breakdowns.map((d) => (
                  <tr key={d.dimension}>
                    <td className="px-3 py-2 font-medium text-ink">{d.dimension.replace(/_/g, " ")}</td>
                    <td className="px-3 py-2 tabular">{d.unknown ? "—" : d.raw_score}</td>
                    <td className="px-3 py-2 tabular font-semibold">{d.unknown ? "—" : d.adjusted_score}</td>
                    <td className="px-3 py-2 tabular">{d.unknown ? "0%" : `${Math.round(d.confidence * 100)}%`}</td>
                    <td className="px-3 py-2 tabular">{d.unknown ? "0%" : `${Math.round(d.coverage * 100)}%`}</td>
                    <td className="px-3 py-2">
                      {d.unknown ? (
                        <span className="text-xs font-semibold text-missing">Unknown</span>
                      ) : d.contradiction_count > 0 ? (
                        <span className="text-xs font-semibold text-contradiction">Contradiction</span>
                      ) : (
                        <span className="text-xs font-semibold text-verified">Scored</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="panel">
        <h3 className="mb-4 text-lg font-semibold text-ink">Evidence ledger</h3>
        {snapshot.evidence_items.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
            No evidence items yet. Run an assessment to generate structured evidence.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {snapshot.evidence_items.map((ev) => (
              <EvidenceCard key={ev.id} evidence={ev} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
