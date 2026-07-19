import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { CaseStatusBadge } from "@/components/StatusBadge";
import { useApp } from "@/store/appContext";
import { api } from "@/api/client";
import type { BackendOpportunity, BackendFounder } from "@/types/backend";

export default function Cases() {
  const { state } = useApp();
  const [opportunities, setOpportunities] = useState<BackendOpportunity[]>([]);
  const [founders, setFounders] = useState<Record<string, BackendFounder>>({});
  const [liveLoading, setLiveLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLiveLoading(true);
    Promise.all([api.opportunities.list(), api.founders.list()])
      .then(([oppData, founderData]) => {
        if (cancelled) return;
        setOpportunities(oppData);
        const map: Record<string, BackendFounder> = {};
        founderData.forEach((f) => (map[f.id] = f));
        setFounders(map);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLiveLoading(false);
      });
    const interval = setInterval(() => {
      api.opportunities.list().then(setOpportunities).catch(() => {});
    }, 10000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <div className="label mb-1">Live pipeline</div>
          <h1 className="text-2xl font-bold text-ink">Open case files</h1>
          <p className="text-sm text-concrete">Shared screening → validation → associate review → partner decision.</p>
        </div>
      </div>

      {liveLoading && opportunities.length === 0 && (
        <div className="flex items-center gap-2 text-sm text-concrete">
          <Loader2 size={16} className="animate-spin" /> Loading live cases…
        </div>
      )}

      {!liveLoading && opportunities.length === 0 && (
        <div className="rounded-sm border border-concrete/20 bg-manila/20 p-6 text-center text-sm text-concrete">
          No cases yet. Approve a signal from the Discovery inbox to create a founder case.
        </div>
      )}

      {opportunities.length > 0 && (
        <div className="grid grid-cols-1 gap-4">
          {opportunities.map((opp) => {
            const founder = founders[opp.founder_id];
            const status = state.caseOverrides[opp.opportunity_id]?.status || "SCREENING";
            return (
              <Link
                key={opp.opportunity_id}
                to={`/cases/${opp.opportunity_id}`}
                className="index-card group flex flex-col gap-4 border-l-4 border-l-verified hover:border-l-verified/80"
              >
                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-display text-lg font-semibold text-ink">
                        {founder?.current_company || founder?.name || "Untitled opportunity"}
                      </h3>
                      <span className="rounded-sm bg-action/10 px-1.5 py-0.5 text-[10px] font-mono font-semibold uppercase text-action">
                        Live
                      </span>
                    </div>
                    <p className="text-sm text-concrete">
                      {founder?.name ?? opp.founder_id} · Backend opportunity
                    </p>
                  </div>
                  <CaseStatusBadge status={status as any} />
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  <div className="rounded-sm border border-concrete/20 bg-manila/30 p-3">
                    <div className="label">Founder score</div>
                    <div className="mt-1 text-sm font-semibold text-ink">
                      {Math.round(opp.founder_score)} / 100
                    </div>
                  </div>
                  <div className="rounded-sm border border-concrete/20 bg-manila/30 p-3">
                    <div className="label">Confidence</div>
                    <div className="mt-1 font-display text-xl font-bold tabular text-ink">
                      {Math.round(opp.founder_confidence * 100)}%
                    </div>
                  </div>
                  <div className="rounded-sm border border-concrete/20 bg-manila/30 p-3">
                    <div className="label">Market posture</div>
                    <div className="mt-1 text-sm font-semibold text-ink capitalize">{opp.market_posture}</div>
                  </div>
                </div>

                <div className="border-t border-concrete/10 pt-3 text-sm text-concrete">
                  <span className="font-semibold text-ink">Next action:</span>{" "}
                  {state.caseOverrides[opp.opportunity_id]?.nextAction || opp.next_founder_action || "Review opportunity details"}
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
