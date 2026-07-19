import { useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Clock, DollarSign, Eye, Monitor, FileQuestion } from "lucide-react";
import { DEMO_CASES, getDemoPerson, getDemoCompany } from "@/data/demoCases";
import { useApp } from "@/store/appContext";
import { useRole } from "@/store/appContext";
import { CaseStatusBadge } from "@/components/StatusBadge";
import { DemoBadge } from "@/components/DemoBadge";
import { TimeRemaining } from "@/components/TimeRemaining";
import { DriverMiniBars } from "@/components/DriverMiniBars";
import { AxisCard } from "@/components/AxisCard";
import { calculateQueuePriority } from "@/engine/scoring";
import { routeCase } from "@/engine/routing";
import { nextStatusAfterDecision } from "@/engine/routing";
import type { InvestmentCase } from "@/domain/types";

type DecisionType = "INVEST" | "DECLINE" | "MONITOR" | "REQUEST_EVIDENCE";

export default function Decisions() {
  const { state, setCaseOverride, recordDecision } = useApp();
  const role = useRole();
  const [overrideReason, setOverrideReason] = useState("");
  const [requestedEvidence, setRequestedEvidence] = useState("");
  const [stamps, setStamps] = useState<Record<string, DecisionType | null>>({});

  const eligibleCases = DEMO_CASES.filter((c) => {
    const override = state.caseOverrides[c.id] || {};
    const status = (override.status || c.status) as InvestmentCase["status"];
    return ["ASSOCIATE_REVIEW", "PARTNER_REVIEW", "VALIDATION_HOLD"].includes(status);
  });

  const handleDecide = (c: InvestmentCase, decision: DecisionType) => {
    setStamps((prev) => ({ ...prev, [c.id]: decision }));
    const next = nextStatusAfterDecision(decision, c.status);
    setTimeout(() => {
      setCaseOverride(c.id, { status: next });
      recordDecision(c.id, {
        caseId: c.id,
        role,
        decision,
        overrideReason: decision === "INVEST" || decision === "DECLINE" ? overrideReason : undefined,
        requestedEvidence: decision === "REQUEST_EVIDENCE" ? requestedEvidence : undefined,
        recordedAt: new Date().toISOString(),
      });
      setTimeout(() => setStamps((prev) => ({ ...prev, [c.id]: null })), 900);
    }, 400);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <div className="label mb-1">Partner Decision Queue</div>
          <h1 className="text-2xl font-bold text-ink">$100K checks on the desk</h1>
          <p className="text-sm text-concrete">One decision every 4–5 days. 24h SLA.</p>
        </div>
        <DemoBadge />
      </div>

      {role !== "PARTNER" && (
        <div className="rounded-sm border border-uncertain/30 bg-uncertain/10 p-3 text-sm text-uncertain">
          <AlertTriangle size={16} className="inline" /> Switch to the Partner role to see decision controls.
        </div>
      )}

      <div className="grid grid-cols-1 gap-6">
        {eligibleCases.map((c) => {
          const override = state.caseOverrides[c.id] || {};
          const status = (override.status || c.status) as InvestmentCase["status"];
          const isHold = status === "VALIDATION_HOLD";
          const company = c.companyId ? getDemoCompany(c.companyId) : undefined;
          const founders = c.founderIds.map((id) => getDemoPerson(id)).filter(Boolean);
          const priority = calculateQueuePriority(c.drivers);
          const routed = routeCase(c);
          const coverage = Math.round((c.drivers.filter((d) => d.confidence >= 0.5).length / 6) * 100);
          const stamp = stamps[c.id];
          return (
            <div key={c.id} className="panel relative space-y-5">
              {stamp && (
                <div className="stamp stamp-visible">
                  <div className={`stamp-mark ${stamp === "INVEST" ? "stamp-invest" : ""}`}>
                    {stamp === "INVEST" ? "Approved" : stamp === "DECLINE" ? "Declined" : stamp === "MONITOR" ? "Monitor" : "Evidence"}
                  </div>
                </div>
              )}
              <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-display text-xl font-bold text-ink">
                      {company?.name || founders.map((f) => f?.name).join(" & ")}
                    </h3>
                    <CaseStatusBadge status={status} />
                    <DemoBadge />
                  </div>
                  <p className="text-sm text-concrete">
                    {founders.map((f) => f?.name).join(", ")} · {c.inboundOrOutbound} · {c.sourceChannel}
                  </p>
                </div>
                <div className="text-right">
                  <div className="label">Operational priority</div>
                  <div className="font-display text-3xl font-bold tabular text-ink">{priority}</div>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
                <Answer title="Why now?" text={c.axes.find((a) => a.key === "MARKET")?.trend || "Unknown"} />
                <Answer title="Why this founder?" text={c.drivers.find((d) => d.key === "FOUNDER")?.rubricReason || "Unknown"} />
                <Answer title="Strongest evidence" text={c.strongestEvidenceClaimIds?.map((id) => id).join(", ") || "None"} />
                <Answer title="What could make us wrong?" text={c.skepticCounterCase || "Unknown"} />
              </div>

              <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
                {c.axes.map((a) => (
                  <AxisCard key={a.key} axis={a} />
                ))}
              </div>

              <div className="rounded-sm border border-concrete/20 bg-manila/30 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <div className="text-sm font-semibold text-ink">Six drivers</div>
                  <div className="text-xs font-mono text-concrete">Trust coverage: {coverage}%</div>
                </div>
                <DriverMiniBars drivers={c.drivers} />
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Metric icon={DollarSign} label="Check size" value="$100,000" />
                <Metric icon={CheckCircle2} label="Thesis result" value={c.thesisResult} />
                <Metric
                  icon={AlertTriangle}
                  label="Contradiction"
                  value={isHold ? "Material unresolved" : "None active"}
                  color={isHold ? "text-contradiction" : "text-verified"}
                />
                <Metric icon={Clock} label="Time remaining" value={<TimeRemaining deadline={c.decisionDeadline} />} />
              </div>

              {isHold && (
                <div className="rounded-sm border border-contradiction/30 bg-contradiction/10 p-3 text-sm text-contradiction">
                  <AlertTriangle size={16} className="inline" /> Invest is disabled. {c.validationHoldReason}
                </div>
              )}

              <div className="flex flex-col gap-3 border-t border-concrete/10 pt-4">
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => handleDecide(c, "INVEST")}
                    disabled={isHold || role !== "PARTNER" || !!stamp}
                    className="rounded-sm bg-verified px-5 py-2 text-sm font-sans font-medium text-paper hover:bg-verified/90 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Invest $100K
                  </button>
                  <button
                    onClick={() => handleDecide(c, "DECLINE")}
                    disabled={role !== "PARTNER" || !!stamp}
                    className="rounded-sm bg-contradiction px-5 py-2 text-sm font-sans font-medium text-paper hover:bg-contradiction/90 disabled:opacity-50"
                  >
                    Decline
                  </button>
                  <button
                    onClick={() => handleDecide(c, "MONITOR")}
                    disabled={!!stamp}
                    className="rounded-sm border border-concrete/30 bg-paper px-5 py-2 text-sm font-sans font-medium text-ink hover:bg-manila/40 disabled:opacity-50"
                  >
                    <Monitor size={16} className="inline" /> Monitor
                  </button>
                  <button
                    onClick={() => handleDecide(c, "REQUEST_EVIDENCE")}
                    disabled={!!stamp}
                    className="rounded-sm border border-concrete/30 bg-paper px-5 py-2 text-sm font-sans font-medium text-ink hover:bg-manila/40 disabled:opacity-50"
                  >
                    <FileQuestion size={16} className="inline" /> Request one item
                  </button>
                  <Link
                    to={`/cases/${c.id}`}
                    className="ml-auto flex items-center gap-1 rounded-sm border border-concrete/30 bg-paper px-4 py-2 text-sm font-sans font-medium text-ink hover:bg-manila/40"
                  >
                    <Eye size={16} /> Open Deal Room
                  </Link>
                </div>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <input
                    className="rounded-sm border border-concrete/30 bg-paper px-3 py-2 text-sm font-sans outline-none"
                    placeholder="Override reason (required for Invest/Decline)"
                    value={overrideReason}
                    onChange={(e) => setOverrideReason(e.target.value)}
                  />
                  <input
                    className="rounded-sm border border-concrete/30 bg-paper px-3 py-2 text-sm font-sans outline-none"
                    placeholder="Specific evidence requested"
                    value={requestedEvidence}
                    onChange={(e) => setRequestedEvidence(e.target.value)}
                  />
                </div>
              </div>

              <div className="font-mono text-[10px] uppercase tracking-wide text-concrete">
                Routed state: {routed}. Check size: $100,000. Ownership target: {Math.round((c.termsOwnershipTarget || 0.05) * 100)}%.
              </div>
            </div>
          );
        })}
        {eligibleCases.length === 0 && (
          <div className="panel py-12 text-center text-sm text-concrete">
            No cases in the partner decision queue. Promote a case to Associate Review or resolve a validation hold.
          </div>
        )}
      </div>
    </div>
  );
}

function Answer({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-sm border border-concrete/20 bg-manila/30 p-3">
      <div className="label">{title}</div>
      <div className="mt-1 line-clamp-3 text-sm text-ink">{text}</div>
    </div>
  );
}

function Metric({ icon: Icon, label, value, color }: { icon: React.ElementType; label: string; value: React.ReactNode; color?: string }) {
  return (
    <div className="flex items-center gap-3 rounded-sm border border-concrete/20 bg-paper p-3">
      <Icon size={18} className={color || "text-concrete"} />
      <div>
        <div className="label">{label}</div>
        <div className={`text-sm font-semibold ${color || "text-ink"}`}>{value}</div>
      </div>
    </div>
  );
}
