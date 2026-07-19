import { useState, useMemo, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  FileText,
  History,
  LayoutDashboard,
  Loader2,
  MessageSquare,
  Monitor,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  Upload,
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
import { api } from "@/api/client";
import type { BackendOpportunity, BackendFounder, BackendClaim, ApiError } from "@/types/backend";

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
  const [liveOpportunity, setLiveOpportunity] = useState<BackendOpportunity | null>(null);
  const [liveFounder, setLiveFounder] = useState<BackendFounder | null>(null);
  const [liveClaims, setLiveClaims] = useState<BackendClaim[]>([]);
  const [liveLoading, setLiveLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [liveError, setLiveError] = useState<string | null>(null);

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

  useEffect(() => {
    if (!caseId || baseCase) return;
    let cancelled = false;
    setLiveLoading(true);
    setLiveError(null);
    api.opportunities
      .get(caseId)
      .then((opp) => {
        if (cancelled) return;
        setLiveOpportunity(opp);
        return api.founders.get(opp.founder_id);
      })
      .then((founder) => {
        if (!cancelled && founder) setLiveFounder(founder);
      })
      .catch((err) => {
        if (!cancelled) setLiveError((err as ApiError).message || "Live opportunity not found");
      })
      .finally(() => {
        if (!cancelled) setLiveLoading(false);
      });
    api.opportunities
      .diligence(caseId)
      .then((claims) => {
        if (!cancelled) setLiveClaims(claims);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [caseId, baseCase]);

  useEffect(() => {
    if (!caseId) return;
    const interval = setInterval(() => {
      if (baseCase) return;
      api.opportunities.diligence(caseId).then(setLiveClaims).catch(() => {});
    }, 10000);
    return () => clearInterval(interval);
  }, [caseId, baseCase]);

  if (!investmentCase && !liveOpportunity && !liveLoading) {
    return (
      <div className="panel py-12 text-center">
        <p className="text-concrete">Case not found.</p>
        <Link to="/cases" className="text-action hover:underline">
          Back to cases
        </Link>
      </div>
    );
  }

  if (liveOpportunity) {
    return (
      <LiveOpportunityView
        opportunity={liveOpportunity}
        founder={liveFounder}
        claims={liveClaims}
        loading={liveLoading}
        error={liveError}
        uploading={uploading}
        setUploading={setUploading}
      />
    );
  }

  if (!investmentCase) {
    return (
      <div className="panel py-12 text-center">
        <p className="text-concrete">Loading case…</p>
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

      <div className="panel space-y-4 border-manila-dark/30 bg-manila/20">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-ink">
                {company?.name || founders.map((f) => f?.name).join(" & ") || "Untitled case"}
              </h1>
              <DemoBadge />
            </div>
            <p className="text-sm text-concrete">
              {founders.map((f) => `${f?.name} (${f?.role})`).join(", ")} · {investmentCase.inboundOrOutbound} ·{" "}
              {investmentCase.sourceChannel}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <CaseStatusBadge status={investmentCase.status} />
            <div className="rounded-sm border border-concrete/20 bg-paper px-3 py-1.5 text-sm">
              <span className="text-concrete">Owner:</span>{" "}
              <span className="font-sans font-medium text-ink">{investmentCase.owner}</span>
            </div>
            <div className="rounded-sm border border-concrete/20 bg-paper px-3 py-1.5 text-sm">
              <span className="text-concrete">Thesis:</span>{" "}
              <span className={`font-sans font-medium ${investmentCase.thesisResult === "ELIGIBLE" ? "text-verified" : "text-uncertain"}`}>
                {investmentCase.thesisResult}
              </span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-sm border border-concrete/20 bg-paper p-3">
            <div className="label">Operational priority</div>
            <div className="font-display text-xl font-bold tabular text-ink">{priority}</div>
          </div>
          <div className="rounded-sm border border-concrete/20 bg-paper p-3">
            <div className="label">Routed state</div>
            <div className="text-sm font-semibold text-ink">{routed}</div>
          </div>
          <div className="rounded-sm border border-concrete/20 bg-paper p-3">
            <div className="label">Next action</div>
            <div className="text-sm text-ink">{investmentCase.nextAction}</div>
          </div>
          <div className="rounded-sm border border-concrete/20 bg-paper p-3">
            <div className="label">24h SLA</div>
            <TimeRemaining deadline={investmentCase.decisionDeadline} />
          </div>
        </div>

        {isHold && (
          <div className="flex items-start gap-3 rounded-sm border border-contradiction/30 bg-contradiction/10 p-3 text-sm text-contradiction">
            <AlertTriangle size={18} />
            <div>
              <div className="font-semibold">Validation hold</div>
              <div>{investmentCase.validationHoldReason}</div>
            </div>
          </div>
        )}
      </div>

      <ActionPanel
        isHold={isHold}
        role={role}
        onResolve={handleResolve}
        resolving={resolving}
        onDecision={handleDecision}
      />

      <div className="border-b border-concrete/20">
        <div className="flex gap-1 overflow-x-auto">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 whitespace-nowrap border-b-2 px-4 py-2 text-sm font-sans font-medium transition ${
                  activeTab === tab.id
                    ? "border-action text-action"
                    : "border-transparent text-concrete hover:text-ink"
                }`}
              >
                <Icon size={16} /> {tab.label}
                {tab.id === "evidence" && contradictedClaims.length > 0 && (
                  <span className="rounded-full bg-contradiction/10 px-1.5 py-0 text-[10px] font-bold text-contradiction">
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
        </div>
      )}

      {activeTab === "deck" && (
        <div className="space-y-6">
          {deckExtraction ? (
            <div className="panel space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-display text-lg font-semibold text-ink">Deck extraction</h3>
                <span className="rounded-sm bg-manila/60 px-2 py-1 text-[10px] font-mono font-semibold text-concrete">
                  Demo fixture
                </span>
              </div>
              <DeckClaimTable
                claims={investmentCase.claims.filter((c) => c.sourceRefs.some((s) => s.sourceType === "DECK"))}
                selectedId={selectedClaimId}
                onSelect={(id) => {
                  setSelectedClaimId(id);
                }}
              />
              {deckExtraction.missingSections.length > 0 && (
                <div className="text-sm text-concrete">
                  <span className="font-semibold text-ink">Missing sections:</span>{" "}
                  {deckExtraction.missingSections.join(", ")}
                </div>
              )}
            </div>
          ) : (
            <div className="panel text-sm text-concrete">No deck uploaded for this case.</div>
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
              <div className="mt-3 text-sm text-concrete">
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
            <h3 className="font-display text-lg font-semibold text-ink">All claims</h3>
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
                <div key={c.id} className="rounded-sm bg-contradiction/10 p-3 text-sm">
                  <div className="font-medium text-contradiction">{c.text}</div>
                  <div className="mt-1 text-contradiction/80">
                    Source: {c.sourceRefs.map((s) => s.title).join(", ")} · Trust: {Math.round(c.trustScore * 100)}%
                  </div>
                </div>
              ))}
              <button
                onClick={handleResolve}
                disabled={resolving}
                className="rounded-sm bg-action px-4 py-2 text-sm font-sans font-medium text-paper hover:bg-action-dark disabled:opacity-50"
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

function LiveOpportunityView({
  opportunity,
  founder,
  claims,
  loading,
  error,
  uploading,
  setUploading,
}: {
  opportunity: BackendOpportunity;
  founder: BackendFounder | null;
  claims: BackendClaim[];
  loading: boolean;
  error: string | null;
  uploading: boolean;
  setUploading: (v: boolean) => void;
}) {
  const [uploadError, setUploadError] = useState<string | null>(null);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      await api.opportunities.uploadDeck(opportunity.opportunity_id, file, founder?.id);
      alert("Deck uploaded. Extraction is running in the background.");
    } catch (err) {
      setUploadError((err as ApiError).message || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Link to="/cases" className="text-sm text-action hover:underline">
          <ArrowLeft size={16} className="inline" /> Cases
        </Link>
      </div>

      <div className="panel space-y-4 border-manila-dark/30 bg-manila/20">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-ink">
                {founder?.current_company || founder?.name || "Untitled opportunity"}
              </h1>
              <span className="rounded-sm bg-action/10 px-1.5 py-0.5 text-[10px] font-mono font-semibold uppercase text-action">
                Live
              </span>
            </div>
            <p className="text-sm text-concrete">
              {founder?.name ?? opportunity.founder_id} · Backend opportunity · Score{" "}
              {Math.round(opportunity.founder_score * 100)}/100
            </p>
          </div>
          <CaseStatusBadge status="SCREENING" />
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-sm border border-concrete/20 bg-paper p-3">
            <div className="label">Founder score</div>
            <div className="font-display text-xl font-bold tabular text-ink">
              {Math.round(opportunity.founder_score * 100)}
            </div>
          </div>
          <div className="rounded-sm border border-concrete/20 bg-paper p-3">
            <div className="label">Confidence</div>
            <div className="font-display text-xl font-bold tabular text-ink">
              {Math.round(opportunity.founder_confidence * 100)}%
            </div>
          </div>
          <div className="rounded-sm border border-concrete/20 bg-paper p-3">
            <div className="label">Market posture</div>
            <div className="text-sm font-semibold text-ink capitalize">{opportunity.market_posture}</div>
          </div>
          <div className="rounded-sm border border-concrete/20 bg-paper p-3">
            <div className="label">Idea vs market</div>
            <div className="text-sm font-semibold text-ink capitalize">{opportunity.idea_vs_market_posture}</div>
          </div>
        </div>

        <div className="border-t border-concrete/10 pt-3 text-sm text-concrete">
          <span className="font-semibold text-ink">Next action:</span>{" "}
          {opportunity.next_founder_action || "Review opportunity details"}
        </div>
      </div>

      <div className="panel space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-display text-lg font-semibold text-ink">Diligence claims</h3>
          <label className={`flex cursor-pointer items-center gap-2 rounded-sm bg-action px-4 py-2 text-sm font-sans font-medium text-paper hover:bg-action-dark ${uploading ? "opacity-50" : ""}`}>
            {uploading ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
            {uploading ? "Uploading…" : "Upload deck"}
            <input type="file" className="hidden" accept=".pdf,.docx,.txt,.md" onChange={handleUpload} disabled={uploading} />
          </label>
        </div>
        {uploadError && (
          <div className="rounded-sm border border-contradiction/30 bg-contradiction/10 p-3 text-sm text-contradiction">
            <AlertTriangle size={16} className="inline" /> {uploadError}
          </div>
        )}
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-concrete">
            <Loader2 size={16} className="animate-spin" /> Loading…
          </div>
        ) : error ? (
          <div className="text-sm text-contradiction">{error}</div>
        ) : claims.length === 0 ? (
          <div className="text-sm text-concrete">No claims extracted yet. Upload a deck to create claims.</div>
        ) : (
          <div className="space-y-2">
            {claims.map((claim) => (
              <div
                key={claim.id}
                className={`rounded-sm border p-3 ${
                  claim.trust_status === "contradicted" ? "border-contradiction/20 bg-contradiction/5" : "border-concrete/20 bg-paper"
                }`}
              >
                <div className="font-sans text-sm font-medium text-ink">{claim.claim}</div>
                <div className="mt-1 text-xs text-concrete">
                  Source: {claim.source} · Trust: {claim.trust_status} · Confidence:{" "}
                  {Math.round(claim.confidence * 100)}%
                </div>
                {claim.contradiction && (
                  <div className="mt-1 text-xs text-contradiction">Contradiction: {claim.contradiction}</div>
                )}
                {claim.next_action && (
                  <div className="mt-1 text-xs text-action">Next: {claim.next_action}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="panel space-y-4">
        <h3 className="font-display text-lg font-semibold text-ink">Founder-market fit</h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {Object.entries(opportunity.founder_market_fit).map(([key, value]) => {
            if (typeof value !== "number" || key === "confidence" || key === "coverage") return null;
            return (
              <div key={key} className="rounded-sm border border-concrete/20 bg-paper p-3">
                <div className="label">{key.replace(/_/g, " ")}</div>
                <div className="font-display text-lg font-bold tabular text-ink">{Math.round(value * 100)}%</div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="panel space-y-4">
        <h3 className="font-display text-lg font-semibold text-ink">Team completeness</h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {Object.entries(opportunity.team_completeness).map(([key, value]) => {
            if (typeof value !== "number" || key === "confidence" || key === "coverage") return null;
            return (
              <div key={key} className="rounded-sm border border-concrete/20 bg-paper p-3">
                <div className="label">{key.replace(/_/g, " ")}</div>
                <div className="font-display text-lg font-bold tabular text-ink">{Math.round(value * 100)}%</div>
              </div>
            );
          })}
        </div>
        {opportunity.team_completeness.missing_critical_roles &&
          opportunity.team_completeness.missing_critical_roles.length > 0 && (
            <div className="text-sm text-concrete">
              Missing roles: {opportunity.team_completeness.missing_critical_roles.join(", ")}
            </div>
          )}
      </div>
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
        <button className="rounded-sm border border-concrete/30 bg-paper px-4 py-2 text-sm font-sans font-medium text-ink hover:bg-manila/40">
          <UserCog size={16} className="inline" /> Assign diligence
        </button>
        <button className="rounded-sm border border-concrete/30 bg-paper px-4 py-2 text-sm font-sans font-medium text-ink hover:bg-manila/40">
          <MessageSquare size={16} className="inline" /> Ask founder
        </button>
        <button
          onClick={onResolve}
          disabled={resolving}
          className="rounded-sm border border-concrete/30 bg-paper px-4 py-2 text-sm font-sans font-medium text-ink hover:bg-manila/40 disabled:opacity-50"
        >
          <CheckCircle2 size={16} className="inline" /> Resolve contradiction
        </button>
        <button className="rounded-sm border border-concrete/30 bg-paper px-4 py-2 text-sm font-sans font-medium text-ink hover:bg-manila/40">
          <TrendingUp size={16} className="inline" /> Advance to Associate
        </button>
        <button
          onClick={() => onDecision("MONITOR")}
          className="rounded-sm border border-concrete/30 bg-paper px-4 py-2 text-sm font-sans font-medium text-ink hover:bg-manila/40"
        >
          <Monitor size={16} className="inline" /> Monitor
        </button>
        <button
          onClick={() => onDecision("DECLINE")}
          className="rounded-sm border border-concrete/30 bg-paper px-4 py-2 text-sm font-sans font-medium text-contradiction hover:bg-contradiction/10"
        >
          <XCircle size={16} className="inline" /> Decline
        </button>
      </div>
      {role === "PARTNER" && (
        <div className="flex flex-wrap gap-2 border-t border-concrete/10 pt-4">
          <button
            onClick={() => onDecision("INVEST")}
            disabled={isHold}
            className="rounded-sm bg-verified px-5 py-2 text-sm font-sans font-medium text-paper hover:bg-verified/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Invest $100K
          </button>
          <button
            onClick={() => onDecision("DECLINE")}
            className="rounded-sm bg-contradiction px-5 py-2 text-sm font-sans font-medium text-paper hover:bg-contradiction/90"
          >
            Decline
          </button>
          <button
            onClick={() => onDecision("MONITOR")}
            className="rounded-sm border border-concrete/30 bg-paper px-5 py-2 text-sm font-sans font-medium text-ink hover:bg-manila/40"
          >
            Monitor
          </button>
          <button
            onClick={() => onDecision("REQUEST_EVIDENCE")}
            className="rounded-sm border border-concrete/30 bg-paper px-5 py-2 text-sm font-sans font-medium text-ink hover:bg-manila/40"
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
      <pre className="max-h-60 overflow-auto rounded-sm bg-manila/30 p-3 text-xs text-concrete">
        {JSON.stringify(output, null, 2)}
      </pre>
    </div>
  );
}
