import { Link } from "react-router-dom";
import { DEMO_CASES, getDemoPerson, getDemoCompany } from "@/data/demoCases";
import { CaseStatusBadge } from "@/components/StatusBadge";
import { TimeRemaining } from "@/components/TimeRemaining";
import { DemoBadge } from "@/components/DemoBadge";
import { calculateQueuePriority } from "@/engine/scoring";
import { useApp } from "@/store/appContext";

export default function Cases() {
  const { state } = useApp();
  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <div className="label mb-1">Live pipeline</div>
          <h1 className="text-2xl font-bold text-ink">Open case files</h1>
          <p className="text-sm text-concrete">Shared screening → validation → associate review → partner decision.</p>
        </div>
        <DemoBadge />
      </div>

      <div className="grid grid-cols-1 gap-4">
        {DEMO_CASES.map((c) => {
          const override = state.caseOverrides[c.id] || {};
          const status = override.status || c.status;
          const company = c.companyId ? getDemoCompany(c.companyId) : undefined;
          const founders = c.founderIds.map((id) => getDemoPerson(id)).filter(Boolean);
          return (
            <Link
              key={c.id}
              to={`/cases/${c.id}`}
              className="index-card group flex flex-col gap-4 border-l-4 border-l-action hover:border-l-action-dark"
            >
              <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-display text-lg font-semibold text-ink">
                      {company?.name || founders.map((f) => f?.name).join(" & ") || "Untitled case"}
                    </h3>
                    <DemoBadge />
                  </div>
                  <p className="text-sm text-concrete">
                    {c.inboundOrOutbound} · {c.sourceChannel} · Owner: {override.owner || c.owner}
                  </p>
                </div>
                <CaseStatusBadge status={status} />
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div className="rounded-sm border border-concrete/20 bg-manila/30 p-3">
                  <div className="label">Thesis result</div>
                  <div className="mt-1 text-sm font-semibold text-ink">{c.thesisResult}</div>
                </div>
                <div className="rounded-sm border border-concrete/20 bg-manila/30 p-3">
                  <div className="label">Operational priority</div>
                  <div className="mt-1 font-display text-xl font-bold tabular text-ink">
                    {calculateQueuePriority(c.drivers)}
                  </div>
                </div>
                <div className="rounded-sm border border-concrete/20 bg-manila/30 p-3">
                  <div className="label">24h SLA</div>
                  <div className="mt-1">
                    <TimeRemaining deadline={c.decisionDeadline} />
                  </div>
                </div>
              </div>

              <div className="border-t border-concrete/10 pt-3 text-sm text-concrete">
                <span className="font-semibold text-ink">Next action:</span> {override.nextAction || c.nextAction}
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
