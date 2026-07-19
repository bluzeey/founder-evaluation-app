import { useState, useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  FileText,
  History,
  LayoutDashboard,
  MessageSquare,
  Monitor,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  UserCog,
  XCircle,
} from "lucide-react";
import { getDemoCase, getDemoPerson, getDemoCompany, getDemoDeck } from "@/data/demoCases";
import { useApp } from "@/store/appContext";
import { useRole } from "@/store/appContext";
import { CaseStatusBadge } from "@/components/StatusBadge";
import { DemoBadge } from "@/components/DemoBadge";
import { TimeRemaining } from "@/components/TimeRemaining";
import { DriverCard } from "@/components/DriverCard";
import { AxisCard } from "@/components/AxisCard";
import { DeckClaimTable } from "@/components/DeckClaimTable";
import { MemoView } from "@/components/MemoView";
import { HistoryTimeline } from "@/components/HistoryTimeline";
import { ClaimStatusBadge } from "@/components/StatusBadge";
import { TrustBadge } from "@/components/TrustBadge";
import { calculateQueuePriority } from "@/engine/scoring";
import { routeCase, nextStatusAfterDecision } from "@/engine/routing";
import type { InvestmentCase, CaseStatus } from "@/domain/types";
import { dealCaptain, skeptic, validator, leadAnalyst } from "@/agents";

const TABS = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "deck", label: "Deck & claims", icon: FileText },
  { id: "evidence", label: "Evidence & contradictions", icon: ShieldAlert },
  { id: "drivers", label: "Drivers & axes", icon: TrendingUp },
  { id: "history", label: "History", icon: History },
  { id: "memo", label: "Memo", icon: FileText },
  { id: "agents", label: "Agent activity", icon: Sparkles },
];

export default function DealRoom() {
  const { caseId } = useParams<{ caseId: string }>();
  const { state, setCaseOverride, recordDecision } = useApp();
  const role = useRole();
  const [activeTab, setActiveTab] = useState("overview");
  const [selectedClaimId, setSelectedClaimId] = useState<string | undefined>();
  const [resolving, setResolving] = useState(false);

  const baseCase = useMemo(() => (caseId ? getDemoCase(caseId) : undefined), [caseId]);
  const override = state.caseOverrides[caseId || ""] || {};

  const investmentCase: InvestmentCase | undefined = useMemo(() => {
    if (!baseCase) return undefined;
    return {
      ...baseCase,
      status: (override.status as CaseStatus) || baseCase.status,
      owner: override.owner || baseCase.owner,
      nextAction: override.nextAction || baseCase.nextAction,
    };
  }, [baseCase, override]);

  if (!investmentCase) {
    return (
      <div className="panel py-12 text-center">
        <p className="text-slate-600">Case not found.</p>
        <Link to="/cases" className="text-action hover:underline">
          Back to cases
        </Link>
      </div>
    );
  }

  const company = investmentCase.companyId ? getDemoCompany(investmentCase.companyId) : undefined;
  const founders = investmentCase.founderIds.map((id) => getDemoPerson(id)).filter(Boolean);
  const priority = calculateQueuePriority(investmentCase.drivers);
  const routed = routeCase(investmentCase);
  const deckExtraction = getDemoDeck(investmentCase.id);
  const contradictedClaims = investmentCase.claims.filter((c) => c.status === "CONTRADICTED");
  const isHold = investmentCase.status === "VALIDATION_HOLD";

  const handleResolve = () => {
    setResolving(true);
    setTimeout(() => {
      setCaseOverride(investmentCase.id, {
        status: "DILIGENCE",
        nextAction: "Contradiction resolved in demo. Request bank statement to verify traction.",
      });
      setResolving(false);
    }, 600);
  };

  const handleDecision = (decision: "INVEST" | "DECLINE" | "MONITOR" | "REQUEST_EVIDENCE") => {
    const next = nextStatusAfterDecision(decision, investmentCase.status);
    setCaseOverride(investmentCase.id, { status: next });
    recordDecision(investmentCase.id, {
      caseId: investmentCase.id,
      role,
      decision,
      recordedAt: new Date().toISOString(),
    });
  };

  const openClaim = (id: string) => {
    setSelectedClaimId(id);
    setActiveTab("evidence");
  };

  const selectedClaim = investmentCase.claims.find((c) => c.id === selectedClaimId);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Link to="/cases" className="text-sm text-action hover:underline">
          <ArrowLeft size={16} className="inline" /> Cases
        </Link>
      </div>

      <div className="panel space-y-4">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-ink">
                {company?.name || founders.map((f) => f?.name).join(" & ") || "Untitled case"}
              </h1>
              <DemoBadge />
            </div>
            <p className="text-sm text-slate-600">
              {founders.map((f) => `${f?.name} (${f?.role})`).join(", ")} · {investmentCase.inboundOrOutbound} ·{" "}
              {investmentCase.sourceChannel}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <CaseStatusBadge status={investmentCase.status} />
            <div className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm">
              <span className="text-slate-500">Owner:</span> <span className="font-medium text-ink">{investmentCase.owner}</span>
            </div>
            <div className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm">
              <span className="text-slate-500">Thesis:</span>{" "}
              <span className={`font-medium ${investmentCase.thesisResult === "ELIGIBLE" ? "text-verified" : "text-uncertain"}`}>
                {investmentCase.thesisResult}
              </span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-lg border border-slate-200 p-3">
            <div className="text-[10px] font-semibold uppercase text-slate-500">Operational priority</div>
            <div className="text-xl font-bold tabular text-ink">{priority}</div>
          </div>
          <div className="rounded-lg border border-slate-200 p-3">
            <div className="text-[10px] font-semibold uppercase text-slate-500">Routed state</div>
            <div className="text-sm font-semibold text-ink">{routed}</div>
          </div>
          <div className="rounded-lg border border-slate-200 p-3">
            <div className="text-[10px] font-semibold uppercase text-slate-500">Next action</div>
            <div className="text-sm text-ink">{investmentCase.nextAction}</div>
          </div>
          <div className="rounded-lg border border-slate-200 p-3">
            <div className="text-[10px] font-semibold uppercase text-slate-500">24h SLA</div>
            <TimeRemaining deadline={investmentCase.decisionDeadline} />
          </div>
        </div>

        {isHold && (
          <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            <AlertTriangle size={18} />
            <div>
              <div className="font-semibold">Validation hold</div>
              <div>{investmentCase.validationHoldReason}</div>
            </div>
          </div>
        )}
      </div>

      <div className="border-b border-slate-200">
        <div className="flex gap-1 overflow-x-auto">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 whitespace-nowrap border-b-2 px-4 py-2 text-sm font-medium transition ${
                  activeTab === tab.id
                    ? "border-action text-action"
                    : "border-transparent text-slate-500 hover:text-ink"
                }`}
              >
                <Icon size={16} /> {tab.label}
                {tab.id === "evidence" && contradictedClaims.length > 0 && (
                  <span className="rounded-full bg-red-100 px-1.5 py-0 text-[10px] font-bold text-contradiction">
                    {contradictedClaims.length}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {activeTab === "overview" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
            {investmentCase.axes.map((a) => (
              <AxisCard key={a.key} axis={a} />
            ))}
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {investmentCase.drivers.map((d) => (
              <DriverCard key={d.key} driver={d} onClaimClick={openClaim} />
            ))}
          </div>
          <ActionPanel
            isHold={isHold}
            role={role}
            onResolve={handleResolve}
            resolving={resolving}
            onDecision={handleDecision}
          />
        </div>
      )}

      {activeTab === "deck" && (
        <div className="space-y-6">
          {deckExtraction ? (
            <div className="panel space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-ink">Deck extraction</h3>
                <span className="rounded bg-slate-100 px-2 py-1 text-[10px] font-semibold text-slate-600">
                  Demo fixture
                </span>
              </div>
              <DeckClaimTable
                claims={investmentCase.claims.filter((c) => c.sourceRefs.some((s) => s.sourceType === "DECK"))}
                selectedId={selectedClaimId}
                onSelect={(id) => {
                  setSelectedClaimId(id);
                  // Scroll to slide could be implemented here.
                }}
              />
              {deckExtraction.missingSections.length > 0 && (
                <div className="text-sm text-slate-600">
                  <span className="font-semibold">Missing sections:</span>{" "}
                  {deckExtraction.missingSections.join(", ")}
                </div>
              )}
            </div>
          ) : (
            <div className="panel text-sm text-slate-500">No deck uploaded for this case.</div>
          )}
        </div>
      )}

      {activeTab === "evidence" && (
        <div className="space-y-6">
          {selectedClaim && (
            <div className="panel border-l-4 border-l-action">
              <div className="label mb-2">Selected claim</div>
              <div className="text-lg font-medium text-ink">{selectedClaim.text}</div>
              <div className="mt-2 flex flex-wrap gap-2">
                <ClaimStatusBadge status={selectedClaim.status} />
                <TrustBadge score={selectedClaim.trustScore} />
              </div>
              <div className="mt-3 text-sm text-slate-600">
                Sources: {" "}
                {selectedClaim.sourceRefs.map((s) => `${s.title}${s.slide ? ` (slide ${s.slide})` : ""}`).join(", ")}
              </div>
              {selectedClaim.contradictionOf && (
                <div className="mt-2 text-sm text-contradiction">
                  Contradicts claim {selectedClaim.contradictionOf}
                </div>
              )}
            </div>
          )}
          <div className="panel space-y-4">
            <h3 className="text-lg font-semibold text-ink">All claims</h3>
            <DeckClaimTable
              claims={investmentCase.claims}
              selectedId={selectedClaimId}
              onSelect={setSelectedClaimId}
            />
          </div>
          {contradictedClaims.length > 0 && (
            <div className="panel space-y-3 border-l-4 border-l-contradiction">
              <div className="flex items-center gap-2 text-lg font-semibold text-contradiction">
                <AlertTriangle size={18} /> Contradictions
              </div>
              {contradictedClaims.map((c) => (
                <div key={c.id} className="rounded-lg bg-red-50 p-3 text-sm">
                  <div className="font-medium text-red-800">{c.text}</div>
                  <div className="mt-1 text-red-700">
                    Source: {c.sourceRefs.map((s) => s.title).join(", ")} · Trust: {Math.round(c.trustScore * 100)}%
                  </div>
                </div>
              ))}
              <button
                onClick={handleResolve}
                disabled={resolving}
                className="rounded-lg bg-action px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {resolving ? "Resolving…" : "Resolve contradiction (demo)"}
              </button>
            </div>
          )}
        </div>
      )}

      {activeTab === "drivers" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
            {investmentCase.axes.map((a) => (
              <AxisCard key={a.key} axis={a} />
            ))}
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {investmentCase.drivers.map((d) => (
              <DriverCard key={d.key} driver={d} onClaimClick={openClaim} />
            ))}
          </div>
        </div>
      )}

      {activeTab === "history" && <HistoryTimeline events={investmentCase.history} />}

      {activeTab === "memo" && investmentCase.memo && <MemoView memo={investmentCase.memo} />}

      {activeTab === "agents" && (
        <div className="space-y-4">
          <AgentCard title="Lead Analyst" output={leadAnalyst({ investmentCase, claims: investmentCase.claims, role })} />
          <AgentCard title="Deal Captain" output={dealCaptain({ investmentCase, claims: investmentCase.claims, role })} />
          <AgentCard title="Skeptic" output={skeptic({ investmentCase, claims: investmentCase.claims, role })} />
          <AgentCard title="Validator" output={validator({ investmentCase, claims: investmentCase.claims, role })} />
        </div>
      )}
    </div>
  );
}

function ActionPanel({
  isHold,
  role,
  onResolve,
  resolving,
  onDecision,
}: {
  isHold: boolean;
  role: string;
  onResolve: () => void;
  resolving: boolean;
  onDecision: (d: "INVEST" | "DECLINE" | "MONITOR" | "REQUEST_EVIDENCE") => void;
}) {
  return (
    <div className="panel space-y-4">
      <div className="text-sm font-semibold text-ink">Actions</div>
      <div className="flex flex-wrap gap-2">
        <button className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
          <UserCog size={16} className="inline" /> Assign diligence
        </button>
        <button className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
          <MessageSquare size={16} className="inline" /> Ask founder
        </button>
        <button
          onClick={onResolve}
          disabled={resolving}
          className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          <CheckCircle2 size={16} className="inline" /> Resolve contradiction
        </button>
        <button className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
          <TrendingUp size={16} className="inline" /> Advance to Associate
        </button>
        <button
          onClick={() => onDecision("MONITOR")}
          className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          <Monitor size={16} className="inline" /> Monitor
        </button>
        <button
          onClick={() => onDecision("DECLINE")}
          className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50"
        >
          <XCircle size={16} className="inline" /> Decline
        </button>
      </div>
      {role === "PARTNER" && (
        <div className="flex flex-wrap gap-2 border-t border-slate-200 pt-4">
          <button
            onClick={() => onDecision("INVEST")}
            disabled={isHold}
            className="rounded-lg bg-green-600 px-5 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Invest $100K
          </button>
          <button
            onClick={() => onDecision("DECLINE")}
            className="rounded-lg bg-red-600 px-5 py-2 text-sm font-medium text-white hover:bg-red-700"
          >
            Decline
          </button>
          <button
            onClick={() => onDecision("MONITOR")}
            className="rounded-lg border border-slate-300 bg-white px-5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Monitor
          </button>
          <button
            onClick={() => onDecision("REQUEST_EVIDENCE")}
            className="rounded-lg border border-slate-300 bg-white px-5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Request evidence
          </button>
        </div>
      )}
      {isHold && (
        <div className="text-xs text-contradiction">
          Invest is disabled because the case is on validation hold. Resolve the contradiction first.
        </div>
      )}
    </div>
  );
}

function AgentCard({ title, output }: { title: string; output: unknown }) {
  return (
    <div className="panel">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink">
        <Sparkles size={16} className="text-uncertain" /> {title}
      </div>
      <pre className="max-h-60 overflow-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
        {JSON.stringify(output, null, 2)}
      </pre>
    </div>
  );
}
