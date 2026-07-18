import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, HelpCircle, ClipboardCheck } from "lucide-react";
import { api } from "@/lib/api";
import ScoreCapsule from "@/components/ScoreCapsule";
import DimensionRow from "@/components/DimensionRow";
import type { Founder, ScoreSnapshot } from "@/types";

export default function FounderProfile() {
  const { founderId } = useParams<{ founderId: string }>();
  const [founder, setFounder] = useState<Founder | null>(null);
  const [snapshot, setSnapshot] = useState<ScoreSnapshot | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!founderId) return;
    (async () => {
      setLoading(true);
      const [f, s] = await Promise.all([api.getFounder(founderId), api.getScore(founderId)]);
      setFounder(f);
      setSnapshot(s);
      setLoading(false);
    })();
  }, [founderId]);

  if (loading) return <div className="panel py-12 text-center">Loading profile…</div>;
  if (!founder || !snapshot) return <div className="panel py-12 text-center">Founder not found.</div>;

  const unknowns = snapshot.dimension_breakdowns.filter((d) => d.unknown);
  const contradictions = snapshot.dimension_breakdowns.filter((d) => d.contradiction_count > 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
        <div>
          <h1 className="text-2xl font-bold text-ink">{founder.name}</h1>
          <p className="text-slate-600">
            {founder.role} · {founder.current_company} · {founder.location}
          </p>
        </div>
        <div className="flex gap-3">
          <Link
            to={`/assessment/${founder.id}`}
            className="flex items-center gap-2 rounded-lg bg-action px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            <ClipboardCheck size={16} /> Invite assessment
          </Link>
          <Link
            to={`/founders/${founder.id}/score`}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Explore score
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <ScoreCapsule snapshot={snapshot} size="lg" />
        </div>

        <div className="space-y-4 lg:col-span-1">
          <div className="panel">
            <h3 className="mb-3 text-lg font-semibold text-ink">Interpretation</h3>
            {unknowns.length > 0 && (
              <div className="mb-4">
                <div className="label mb-1.5 flex items-center gap-1.5 text-missing">
                  <HelpCircle size={14} /> Unknowns
                </div>
                <ul className="space-y-1 text-sm text-slate-700">
                  {unknowns.map((u) => (
                    <li key={u.dimension}>• {u.dimension.replace(/_/g, " ")}</li>
                  ))}
                </ul>
              </div>
            )}
            {contradictions.length > 0 && (
              <div>
                <div className="label mb-1.5 flex items-center gap-1.5 text-contradiction">
                  <AlertTriangle size={14} /> Contradictions
                </div>
                <ul className="space-y-1 text-sm text-slate-700">
                  {contradictions.map((c) => (
                    <li key={c.dimension}>• {c.dimension.replace(/_/g, " ")}</li>
                  ))}
                </ul>
              </div>
            )}
            {unknowns.length === 0 && contradictions.length === 0 && (
              <p className="text-sm text-slate-600">No critical unknowns or contradictions.</p>
            )}
          </div>

          <div className="panel">
            <h3 className="mb-3 text-lg font-semibold text-ink">Current opportunity</h3>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-600">Founder-market fit</span>
                <span className="font-semibold text-ink">Not assessed</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-600">Team completeness</span>
                <span className="font-semibold text-ink">Not assessed</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-600">Thesis match</span>
                <span className="font-semibold text-verified">High</span>
              </div>
            </div>
          </div>
        </div>

        <div className="panel lg:col-span-1">
          <h3 className="mb-3 text-lg font-semibold text-ink">Next best action</h3>
          <p className="mb-4 text-sm text-slate-600">
            {snapshot.overall_confidence < 0.45
              ? "Generate structured evidence through the cold-start assessment modules."
              : "Review evidence ledger and resolve remaining unknowns before decision."}
          </p>
          <Link
            to={`/assessment/${founder.id}`}
            className="block w-full rounded-lg bg-action py-2.5 text-center text-sm font-medium text-white hover:bg-blue-700"
          >
            Start assessment
          </Link>
        </div>
      </div>

      <div className="panel">
        <h2 className="mb-4 text-xl font-semibold text-ink">Capability dimensions</h2>
        <div className="space-y-3">
          {snapshot.dimension_breakdowns.map((b) => (
            <DimensionRow key={b.dimension} breakdown={b} />
          ))}
        </div>
      </div>
    </div>
  );
}
