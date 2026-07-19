import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { Loader2, RotateCw, AlertCircle } from "lucide-react";
import { api } from "@/api/client";
import { useAdaptivePolling } from "@/hooks/useAdaptivePolling";
import { CaseStatusBadge } from "@/components/StatusBadge";
import { CaseStatusActions } from "@/components/CaseStatusActions";
import type { ApiError, BackendFounder, BackendOpportunity } from "@/types/backend";
import type { CaseStatus } from "@/domain/types";

const DECISION_STATUSES: CaseStatus[] = ["DILIGENCE", "ASSOCIATE_REVIEW", "PARTNER_REVIEW"];

export default function Decisions() {
  const [opportunities, setOpportunities] = useState<BackendOpportunity[]>([]);
  const [founders, setFounders] = useState<Record<string, BackendFounder>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [oppData, founderData] = await Promise.all([
        api.opportunities.list(),
        api.founders.list(),
      ]);
      setOpportunities(oppData);
      const map: Record<string, BackendFounder> = {};
      founderData.forEach((f) => (map[f.id] = f));
      setFounders(map);
      setError(null);
    } catch (err) {
      setError((err as ApiError).message || "Failed to load decision queue");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const queue = opportunities.filter((opp) =>
    DECISION_STATUSES.includes((opp.status as CaseStatus) || "SCREENING")
  );
  useAdaptivePolling(refresh, queue.length > 0 ? 10000 : 30000);

  const handleUpdated = (updated: BackendOpportunity) => {
    setOpportunities((prev) => prev.map((o) => (o.opportunity_id === updated.opportunity_id ? updated : o)));
  };

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <div className="label mb-1">Decision pipeline</div>
          <h1 className="text-2xl font-bold text-ink">Decision queue</h1>
          <p className="text-sm text-concrete">
            Active diligence, associate review, and partner review cases. Update status as calls progress.
          </p>
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          className="flex items-center gap-2 rounded-sm border border-concrete/30 bg-paper px-3 py-2 text-sm font-sans font-medium text-ink hover:bg-manila/40 disabled:opacity-50"
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : <RotateCw size={16} />}
          Refresh
        </button>
      </div>

      {error && (
        <div className="rounded-sm border border-contradiction/30 bg-contradiction/10 p-3 text-sm text-contradiction">
          <AlertCircle size={16} className="inline mr-1" />
          {error}
        </div>
      )}

      {loading && queue.length === 0 && (
        <div className="flex items-center gap-2 text-sm text-concrete">
          <Loader2 size={16} className="animate-spin" /> Loading decision queue…
        </div>
      )}

      {!loading && queue.length === 0 && (
        <div className="rounded-sm border border-concrete/20 bg-manila/20 p-6 text-center text-sm text-concrete">
          No cases in the decision pipeline yet. Move a case to the decision queue from its{" "}
          <Link to="/cases" className="text-action hover:underline">
            case file
          </Link>
          .
        </div>
      )}

      <div className="space-y-4">
        {queue.map((opp) => {
          const founder = founders[opp.founder_id];
          return (
            <div key={opp.opportunity_id} className="panel space-y-4">
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-display text-lg font-semibold text-ink">
                      <Link to={`/cases/${opp.opportunity_id}`} className="hover:underline">
                        {founder?.current_company || founder?.name || "Untitled opportunity"}
                      </Link>
                    </h3>
                    <CaseStatusBadge status={(opp.status as CaseStatus) || "SCREENING"} />
                  </div>
                  <p className="text-sm text-concrete">
                    {founder?.name ?? opp.founder_id} · Score {Math.round(opp.founder_score)}/100 · Confidence{" "}
                    {Math.round(opp.founder_confidence * 100)}%
                  </p>
                </div>
                <div className="text-right text-xs text-concrete">
                  <div className="font-semibold text-ink">Next action</div>
                  {opp.next_founder_action || "Review opportunity details"}
                </div>
              </div>

              <CaseStatusActions
                opportunityId={opp.opportunity_id}
                status={(opp.status as CaseStatus) || "SCREENING"}
                onUpdated={handleUpdated}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
