import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { AlertTriangle, HelpCircle, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";
import type { OpportunityScreen as OppType, Claim } from "@/types";

const postureColor = (posture: string) => {
  if (posture.includes("bull") || posture.includes("strong")) return "text-verified bg-green-50";
  if (posture.includes("bear") || posture.includes("weak")) return "text-contradiction bg-red-50";
  return "text-slate-700 bg-slate-100";
};

export default function OpportunityScreen() {
  const { opportunityId } = useParams<{ opportunityId: string }>();
  const [opp, setOpp] = useState<OppType | null>(null);
  const [claims, setClaims] = useState<Claim[]>([]);

  useEffect(() => {
    if (!opportunityId) return;
    (async () => {
      const [o, c] = await Promise.all([api.screenOpportunity(opportunityId), api.getDiligence(opportunityId)]);
      setOpp(o);
      setClaims(c);
    })();
  }, [opportunityId]);

  if (!opp) return <div className="panel py-12 text-center">Loading opportunity screen…</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-ink">Three-axis opportunity screen</h1>
        <Link to="/" className="text-sm text-action hover:underline">
          Back to dashboard
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="panel border-l-4 border-l-action">
          <div className="label mb-2 text-action">Axis 1: Founder</div>
          <div className="mb-3 flex items-baseline justify-between">
            <span className="text-3xl font-bold tabular text-ink">{opp.founder_score}</span>
            <span className="text-sm text-slate-500">{Math.round(opp.founder_confidence * 100)}% confidence</span>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-600">Founder-market fit</span>
              <span className="font-semibold tabular text-ink">
                {opp.founder_market_fit.score ?? "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-600">Team completeness</span>
              <span className="font-semibold tabular text-ink">
                {opp.team_completeness.score ?? "—"}
              </span>
            </div>
          </div>
          <div className="mt-4 text-xs text-slate-500">
            Next action: {opp.next_founder_action}
          </div>
        </div>

        <div className="panel border-l-4 border-l-uncertain">
          <div className="label mb-2 text-uncertain">Axis 2: Market</div>
          <div className="mb-3 flex items-center justify-between">
            <span className={`rounded px-2.5 py-1 text-sm font-bold ${postureColor(opp.market_posture)}`}>
              {opp.market_posture}
            </span>
            <span className="text-sm text-slate-500">{Math.round(opp.market_confidence * 100)}% confidence</span>
          </div>
          <p className="text-sm text-slate-600">
            Market timing, buyer urgency, and competitive dynamics are still being evaluated.
          </p>
        </div>

        <div className="panel border-l-4 border-l-contradiction">
          <div className="label mb-2 text-contradiction">Axis 3: Idea vs. Market</div>
          <div className="mb-3 flex items-center justify-between">
            <span className={`rounded px-2.5 py-1 text-sm font-bold ${postureColor(opp.idea_vs_market_posture)}`}>
              {opp.idea_vs_market_posture}
            </span>
            <span className="text-sm text-slate-500">{Math.round(opp.idea_vs_market_confidence * 100)}% confidence</span>
          </div>
          <p className="text-sm text-slate-600">
            Problem-solution coherence and distribution feasibility need more evidence.
          </p>
        </div>
      </div>

      <div className="panel">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-ink">Diligence claims</h3>
          <span className="text-xs text-slate-500">Every material claim has a status and next action.</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-3 py-2">Claim</th>
                <th className="px-3 py-2">Source</th>
                <th className="px-3 py-2">Trust status</th>
                <th className="px-3 py-2">Confidence</th>
                <th className="px-3 py-2">Contradiction</th>
                <th className="px-3 py-2">Next action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {claims.map((c) => (
                <tr key={c.id}>
                  <td className="px-3 py-3 font-medium text-ink">{c.claim}</td>
                  <td className="px-3 py-3 text-slate-600">{c.source}</td>
                  <td className="px-3 py-3">
                    <span
                      className={`flex items-center gap-1 rounded px-2 py-0.5 text-xs font-semibold ${
                        c.trust_status === "verified"
                          ? "bg-green-50 text-verified"
                          : c.trust_status === "contradicted"
                          ? "bg-red-50 text-contradiction"
                          : c.trust_status === "founder_reported"
                          ? "bg-amber-50 text-uncertain"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {c.trust_status === "verified" && <CheckCircle2 size={12} />}
                      {c.trust_status === "contradicted" && <AlertTriangle size={12} />}
                      {c.trust_status === "founder_reported" && <HelpCircle size={12} />}
                      {c.trust_status.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="px-3 py-3 tabular">{Math.round(c.confidence * 100)}%</td>
                  <td className="px-3 py-3 text-contradiction">{c.contradiction || "—"}</td>
                  <td className="px-3 py-3 text-slate-600">{c.next_action || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
