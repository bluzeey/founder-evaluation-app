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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">Cases</h1>
          <p className="text-sm text-slate-500">Shared screening → validation → associate review → partner decision.</p>
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
              className="panel flex flex-col gap-3 transition hover:border-action"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-lg font-semibold text-ink">
                      {company?.name || founders.map((f) => f?.name).join(" & ") || "Untitled case"}
                    </h3>
                    <DemoBadge />
                  </div>
                  <p className="text-sm text-slate-600">
                    {c.inboundOrOutbound} · {c.sourceChannel} · Owner: {c.owner}
                  </p>
                </div>
                <CaseStatusBadge status={status} />
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="rounded-lg border border-slate-200 p-3">
                  <div className="text-xs text-slate-500">Thesis result</div>
                  <div className="text-sm font-semibold text-ink">{c.thesisResult}</div>
                </div>
                <div className="rounded-lg border border-slate-200 p-3">
                  <div className="text-xs text-slate-500">Operational priority</div>
                  <div className="text-sm font-semibold tabular text-ink">
                    {calculateQueuePriority(c.drivers)}
                  </div>
                </div>
                <div className="rounded-lg border border-slate-200 p-3">
                  <div className="text-xs text-slate-500">24h SLA</div>
                  <TimeRemaining deadline={c.decisionDeadline} />
                </div>
              </div>
              <div className="text-sm text-slate-600">
                <span className="font-semibold">Next action:</span> {override.nextAction || c.nextAction}
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
