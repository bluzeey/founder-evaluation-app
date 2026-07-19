import { useState, useEffect, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Github, Linkedin, Loader2, Upload } from "lucide-react";
import { CaseStatusBadge } from "@/components/StatusBadge";
import { CaseStatusActions } from "@/components/CaseStatusActions";
import { api } from "@/api/client";
import type {
  BackendOpportunity,
  BackendFounder,
  BackendClaim,
  BackendScoreSnapshot,
  BackendDimensionBreakdown,
  ApiError,
} from "@/types/backend";
import type { CaseStatus } from "@/domain/types";

export default function DealRoom() {
  const { caseId } = useParams<{ caseId: string }>();
  const [opportunity, setOpportunity] = useState<BackendOpportunity | null>(null);
  const [founder, setFounder] = useState<BackendFounder | null>(null);
  const [snapshot, setSnapshot] = useState<BackendScoreSnapshot | null>(null);
  const [claims, setClaims] = useState<BackendClaim[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [estimating, setEstimating] = useState(false);
  const [enriching, setEnriching] = useState(false);
  const [enrichStage, setEnrichStage] = useState<string>("");
  const estimateTriggeredRef = useRef<string | null>(null);

  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const opp = await api.opportunities.get(caseId);
        if (cancelled) return;
        setOpportunity(opp);
        const [f, snap] = await Promise.all([
          api.founders.get(opp.founder_id),
          api.founders.score(opp.founder_id),
        ]);
        if (cancelled) return;
        if (f) setFounder(f);
        setSnapshot(snap);

        // Auto-trigger the full enrichment pipeline when the founder is at
        // cold-start (0% confidence, all dimensions unknown). The pipeline
        // runs social research → deep web research → AI estimate via Celery;
        // a separate effect polls enrichment runs + the score until the
        // confidence crosses the threshold.
        const isColdStart = snap.overall_confidence <= 0;
        if (isColdStart && f && estimateTriggeredRef.current !== f.id) {
          estimateTriggeredRef.current = f.id;
          try {
            await api.founders.enrich(f.id);
            if (!cancelled) {
              setEnriching(true);
              setEnrichStage("social");
            }
          } catch {
            // ignore — the backend may also auto-queue from the diligence endpoint
          }
        }
      } catch (err) {
        if (!cancelled) setError((err as ApiError).message || "Case not found");
      } finally {
        if (!cancelled) setLoading(false);
      }
      try {
        const c = await api.opportunities.diligence(caseId);
        if (!cancelled) setClaims(c);
      } catch {
        // ignore diligence errors on initial load
      }
    })();
    const interval = setInterval(() => {
      api.opportunities.diligence(caseId).then(setClaims).catch(() => {});
    }, 10000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [caseId]);

  // Poll the founder score while an AI estimate is running. Stops once the
  // confidence rises above 0 (estimate landed) or after ~60s (timeout).
  useEffect(() => {
    if (!estimating || !founder || !caseId) return;
    let cancelled = false;
    const startedAt = Date.now();
    const poll = setInterval(async () => {
      if (cancelled) return;
      if (Date.now() - startedAt > 60000) {
        setEstimating(false);
        return;
      }
      try {
        const snap = await api.founders.score(founder.id);
        if (cancelled) return;
        setSnapshot(snap);
        if (snap.overall_confidence > 0) {
          setEstimating(false);
          // Refresh the opportunity so the header score/confidence sync.
          try {
            const opp = await api.opportunities.get(caseId);
            if (!cancelled) setOpportunity(opp);
          } catch {
            // ignore
          }
        }
      } catch {
        // ignore polling errors
      }
    }, 3000);
    return () => {
      cancelled = true;
      clearInterval(poll);
    };
  }, [estimating, founder, caseId]);

  // Poll enrichment runs + score while the 3-stage pipeline is running.
  // Shows the current stage and stops once confidence crosses the threshold
  // (0.30) or after ~90s (timeout).
  useEffect(() => {
    if (!enriching || !founder || !caseId) return;
    let cancelled = false;
    const startedAt = Date.now();
    const poll = setInterval(async () => {
      if (cancelled) return;
      if (Date.now() - startedAt > 90000) {
        setEnriching(false);
        return;
      }
      try {
        const [runs, snap] = await Promise.all([
          api.enrichment.runs(founder.id),
          api.founders.score(founder.id),
        ]);
        if (cancelled) return;
        setSnapshot(snap);
        // Derive the current stage from the most recent running run.
        const running = runs.find((r) => r.status === "running");
        if (running) {
          setEnrichStage(running.stage);
        } else {
          // No running stage; pick the latest run's stage for display.
          const latest = runs[0];
          if (latest) setEnrichStage(latest.stage);
        }
        // Stop once the confidence crosses the enrichment threshold.
        if (snap.overall_confidence >= 0.3) {
          setEnriching(false);
          try {
            const opp = await api.opportunities.get(caseId);
            if (!cancelled) setOpportunity(opp);
          } catch {
            // ignore
          }
        }
      } catch {
        // ignore polling errors
      }
    }, 3000);
    return () => {
      cancelled = true;
      clearInterval(poll);
    };
  }, [enriching, founder, caseId]);

  if (loading && !opportunity) {
    return (
      <div className="panel py-12 text-center">
        <div className="flex items-center justify-center gap-2 text-concrete">
          <Loader2 size={16} className="animate-spin" /> Loading case…
        </div>
      </div>
    );
  }

  if (!opportunity) {
    return (
      <div className="panel py-12 text-center">
        <p className="text-concrete">{error || "Case not found."}</p>
        <Link to="/cases" className="text-action hover:underline">
          Back to cases
        </Link>
      </div>
    );
  }

  return (
    <LiveOpportunityView
      opportunity={opportunity}
      founder={founder}
      snapshot={snapshot}
      claims={claims}
      uploading={uploading}
      setUploading={setUploading}
      estimating={estimating}
      enriching={enriching}
      enrichStage={enrichStage}
    />
  );
}

function SocialLink({ href, icon: Icon, label }: { href: string; icon: typeof Linkedin; label: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1 rounded-sm border border-concrete/20 bg-paper px-2 py-1 text-xs font-medium text-action hover:bg-manila/40"
    >
      <Icon size={14} /> {label}
    </a>
  );
}

function isEstimateOnly(
  breakdown: BackendDimensionBreakdown,
  snapshot: BackendScoreSnapshot | null
) {
  if (!snapshot) return false;
  const items = snapshot.evidence_items.filter((item) => item.dimension === breakdown.dimension);
  if (items.length === 0) return false;
  return items.every((item) => item.evidence_type === "inferred_estimate");
}

function stageLabel(stage: string): string {
  switch (stage) {
    case "social":
      return "stage 1/3 social";
    case "deep_web":
      return "stage 2/3 web research";
    case "estimate":
      return "stage 3/3 estimate";
    default:
      return stage ? `stage ${stage}` : "starting";
  }
}

function DimensionCard({
  breakdown,
  snapshot,
}: {
  breakdown: BackendDimensionBreakdown;
  snapshot: BackendScoreSnapshot | null;
}) {
  const name = breakdown.dimension
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
  return (
    <div className="rounded-sm border border-concrete/20 bg-paper p-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div className="label">{name}</div>
        <div className="flex items-center gap-1">
          {breakdown.unknown && (
            <span className="rounded-sm bg-concrete/10 px-1.5 py-0.5 text-[10px] font-medium uppercase text-concrete">
              Unknown
            </span>
          )}
          {!breakdown.unknown && isEstimateOnly(breakdown, snapshot) && (
            <span className="rounded-sm bg-action/10 px-1.5 py-0.5 text-[10px] font-medium uppercase text-action">
              AI estimate
            </span>
          )}
        </div>
      </div>
      <div className="font-display text-xl font-bold tabular text-ink">
        {breakdown.unknown ? "—" : `${Math.round(breakdown.adjusted_score)} / 100`}
      </div>
      <div className="text-xs text-concrete">
        Confidence: {Math.round(breakdown.confidence * 100)}% · Evidence: {breakdown.evidence_count}
        {breakdown.contradiction_count > 0 && ` · Contradictions: ${breakdown.contradiction_count}`}
      </div>
      {breakdown.next_test && (
        <div className="text-xs text-action">Next: {breakdown.next_test}</div>
      )}
      {breakdown.unknowns.length > 0 && (
        <div className="text-xs text-concrete">{breakdown.unknowns[0]}</div>
      )}
    </div>
  );
}

function LiveOpportunityView({
  opportunity,
  founder,
  snapshot,
  claims,
  uploading,
  setUploading,
  estimating,
  enriching,
  enrichStage,
  onStatusUpdated,
}: {
  opportunity: BackendOpportunity;
  founder: BackendFounder | null;
  snapshot: BackendScoreSnapshot | null;
  claims: BackendClaim[];
  uploading: boolean;
  setUploading: (v: boolean) => void;
  estimating: boolean;
  enriching: boolean;
  enrichStage: string;
  onStatusUpdated?: (opp: BackendOpportunity) => void;
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
              {Math.round(opportunity.founder_score)}/100
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {founder?.linkedin_url && (
                <SocialLink href={founder.linkedin_url} icon={Linkedin} label="LinkedIn" />
              )}
              {founder?.github_url && (
                <SocialLink href={founder.github_url} icon={Github} label="GitHub" />
              )}
            </div>
          </div>
          <CaseStatusBadge status={(opportunity.status as CaseStatus) || "SCREENING"} />
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-sm border border-concrete/20 bg-paper p-3">
            <div className="label">Founder score</div>
            <div className="font-display text-xl font-bold tabular text-ink">
              {Math.round(opportunity.founder_score)}
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
        <h3 className="font-display text-lg font-semibold text-ink">Pipeline actions</h3>
        <p className="text-sm text-concrete">
          Move this case into the decision queue or update its status as calls progress.
        </p>
        <CaseStatusActions
          opportunityId={opportunity.opportunity_id}
          status={(opportunity.status as CaseStatus) || "SCREENING"}
          onUpdated={onStatusUpdated}
        />
      </div>

      <div className="panel space-y-3">
        <h3 className="font-display text-lg font-semibold text-ink">Source signal</h3>
        <p className="text-sm font-medium text-ink">
          {founder?.source_reason || "No reason provided."}
        </p>
        {founder?.source_url && (
          <a
            href={founder.source_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-xs text-action hover:underline"
          >
            Source
          </a>
        )}
      </div>

      <div className="panel space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-display text-lg font-semibold text-ink">Founder score breakdown</h3>
          {enriching ? (
            <span className="inline-flex items-center gap-1.5 rounded-sm border border-action/30 bg-action/10 px-2 py-1 text-xs font-mono font-medium text-action">
              <Loader2 size={12} className="animate-spin" /> Enriching ({stageLabel(enrichStage)})…
            </span>
          ) : estimating ? (
            <span className="inline-flex items-center gap-1.5 rounded-sm border border-action/30 bg-action/10 px-2 py-1 text-xs font-mono font-medium text-action">
              <Loader2 size={12} className="animate-spin" /> Estimating score…
            </span>
          ) : null}
        </div>
        {snapshot ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {snapshot.dimension_breakdowns.map((bd) => (
              <DimensionCard key={bd.dimension} breakdown={bd} snapshot={snapshot} />
            ))}
          </div>
        ) : (
          <div className="text-sm text-concrete">No score snapshot available yet.</div>
        )}
      </div>

      <div className="panel space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-display text-lg font-semibold text-ink">Diligence claims</h3>
          <label
            className={`flex cursor-pointer items-center gap-2 rounded-sm bg-action px-4 py-2 text-sm font-sans font-medium text-paper hover:bg-action-dark ${uploading ? "opacity-50" : ""}`}
          >
            {uploading ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
            {uploading ? "Uploading…" : "Upload deck"}
            <input
              type="file"
              className="hidden"
              accept=".pdf,.docx,.txt,.md"
              onChange={handleUpload}
              disabled={uploading}
            />
          </label>
        </div>
        {uploadError && (
          <div className="rounded-sm border border-contradiction/30 bg-contradiction/10 p-3 text-sm text-contradiction">
            <AlertTriangle size={16} className="inline" /> {uploadError}
          </div>
        )}
        {claims.length === 0 ? (
          <div className="text-sm text-concrete">No claims extracted yet. Upload a deck to create claims.</div>
        ) : (
          <div className="space-y-2">
            {claims.map((claim) => (
              <div
                key={claim.id}
                className={`rounded-sm border p-3 ${
                  claim.trust_status === "contradicted"
                    ? "border-contradiction/20 bg-contradiction/5"
                    : "border-concrete/20 bg-paper"
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
