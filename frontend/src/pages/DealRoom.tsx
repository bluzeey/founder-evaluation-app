import { useState, useEffect, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Github, Linkedin, Loader2, Upload } from "lucide-react";
import { CaseStatusBadge } from "@/components/StatusBadge";
import { CaseStatusActions } from "@/components/CaseStatusActions";
import { FourScoreStrip } from "@/features/founders/FourScoreStrip";
import { RecommendationBadge } from "@/features/founders/RecommendationBadge";
import { api, invalidateCache } from "@/api/client";
import { useAdaptivePolling } from "@/hooks/useAdaptivePolling";
import type {
  BackendOpportunity,
  BackendFounder,
  BackendClaim,
  BackendScoreSnapshot,
  BackendFounderScreeningProfile,
  ApiError,
} from "@/types/backend";
import type { CaseStatus } from "@/domain/types";

export default function DealRoom() {
  const { caseId } = useParams<{ caseId: string }>();
  const [opportunity, setOpportunity] = useState<BackendOpportunity | null>(null);
  const [founder, setFounder] = useState<BackendFounder | null>(null);
  const [screeningProfile, setScreeningProfile] = useState<BackendFounderScreeningProfile | null>(null);
  const [claims, setClaims] = useState<BackendClaim[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [estimating, setEstimating] = useState(false);
  const [enriching, setEnriching] = useState(false);
  const estimateTriggeredRef = useRef<string | null>(null);
  const estimateStartedAt = useRef(0);
  const enrichStartedAt = useRef(0);

  useEffect(() => {
    if (estimating) estimateStartedAt.current = Date.now();
  }, [estimating]);

  useEffect(() => {
    if (enriching) enrichStartedAt.current = Date.now();
  }, [enriching]);

  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const [opp, c] = await Promise.all([
          api.opportunities.get(caseId),
          api.opportunities.diligence(caseId).catch(() => [] as BackendClaim[]),
        ]);
        if (cancelled) return;
        setOpportunity(opp);
        setClaims(c);
        const [f, snap] = await Promise.all([
          api.founders.get(opp.founder_id),
          api.founders.score(opp.founder_id).catch(() => null as BackendScoreSnapshot | null),
        ]);
        if (cancelled) return;
        if (f) setFounder(f);
        // snap is used below for cold-start check — no state needed since
        // the legacy Evidence Engine display was removed.
        try {
          const profile = await api.founders.screeningProfile(opp.founder_id);
          if (!cancelled) setScreeningProfile(profile);
        } catch {
          if (!cancelled) setScreeningProfile(null);
        }

        const isColdStart = !snap || snap.overall_confidence <= 0;
        if (
          isColdStart &&
          f &&
          f.enrichment_policy === "AUTO" &&
          estimateTriggeredRef.current !== f.id
        ) {
          estimateTriggeredRef.current = f.id;
          try {
            await api.founders.enrich(f.id);
            if (!cancelled) {
              setEnriching(true);
            }
          } catch {
            // ignore
          }
        }
      } catch (err) {
        if (!cancelled) setError((err as ApiError).message || "Case not found");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  useAdaptivePolling(() => {
    if (!caseId) return;
    api.opportunities.diligence(caseId).then(setClaims).catch(() => {});
  }, caseId ? 10000 : 0);

  useAdaptivePolling(async () => {
    if (!estimating || !founder || !caseId) return;
    if (Date.now() - estimateStartedAt.current > 60000) {
      setEstimating(false);
      return;
    }
    try {
      const snap = await api.founders.score(founder.id);
      if (snap.overall_confidence > 0) {
        setEstimating(false);
        invalidateCache(`/v1/opportunities/${caseId}`);
        try {
          const opp = await api.opportunities.get(caseId);
          setOpportunity(opp);
        } catch {
          // ignore
        }
      }
    } catch {
      // ignore
    }
  }, estimating ? 3000 : 0);

  useAdaptivePolling(async () => {
    if (!enriching || !founder || !caseId) return;
    if (Date.now() - enrichStartedAt.current > 90000) {
      setEnriching(false);
      return;
    }
    try {
      const snap = await api.founders.score(founder.id);
      if (snap.overall_confidence >= 0.3) {
        setEnriching(false);
        invalidateCache(`/v1/opportunities/${caseId}`);
        try {
          const opp = await api.opportunities.get(caseId);
          setOpportunity(opp);
        } catch {
          // ignore
        }
      }
    } catch {
      // ignore
    }
  }, enriching ? 3000 : 0);

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
      screeningProfile={screeningProfile}
      claims={claims}
      uploading={uploading}
      setUploading={setUploading}
      enriching={enriching}
      estimating={estimating}
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

function AssociateScreenCard({
  title,
  score,
  rationale,
  profile,
}: {
  title: string;
  score?: number;
  rationale?: string;
  profile: BackendFounderScreeningProfile;
}) {
  return (
    <div className="rounded-sm border border-concrete/20 bg-paper p-3 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div className="label">{title}</div>
        <div className="font-display text-xl font-bold text-ink">{score ?? "—"}</div>
      </div>
      <p className="text-sm text-ink/80">{rationale || "No rationale recorded."}</p>
      <div className="grid gap-3 text-xs text-concrete sm:grid-cols-3">
        <ListBlock label="Key evidence" items={profile.key_evidence} />
        <ListBlock label="Counter-evidence" items={profile.counter_evidence} />
        <ListBlock label="Unknowns" items={profile.unknowns} />
      </div>
    </div>
  );
}

function ListBlock({ label, items }: { label: string; items: string[] }) {
  return (
    <div>
      <div className="label mb-1">{label}</div>
      {items.length > 0 ? (
        <div className="space-y-1">
          {items.slice(0, 3).map((item) => (
            <div key={`${label}-${item}`} className="rounded-sm bg-manila/20 px-2 py-1 text-ink/80">
              {item}
            </div>
          ))}
        </div>
      ) : (
        <div>—</div>
      )}
    </div>
  );
}

function LiveOpportunityView({
  opportunity,
  founder,
  screeningProfile,
  claims,
  uploading,
  setUploading,
  estimating,
  enriching,
  onStatusUpdated,
}: {
  opportunity: BackendOpportunity;
  founder: BackendFounder | null;
  screeningProfile: BackendFounderScreeningProfile | null;
  claims: BackendClaim[];
  uploading: boolean;
  setUploading: (v: boolean) => void;
  estimating: boolean;
  enriching: boolean;
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
    <div className="space-y-5">
      <div className="flex items-center gap-2">
        <Link to="/cases" className="text-sm text-action hover:underline">
          <ArrowLeft size={16} className="inline" /> Cases
        </Link>
      </div>

      {/* Compact header */}
      <div className="panel space-y-3 border-manila-dark/30 bg-manila/20">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-ink">
                {screeningProfile?.project_name || founder?.current_company || founder?.name || "Untitled"}
              </h1>
              {enriching && (
                <span className="inline-flex items-center gap-1 rounded-sm border border-action/30 bg-action/10 px-1.5 py-0.5 text-[10px] font-mono font-medium text-action">
                  <Loader2 size={10} className="animate-spin" /> Enriching
                </span>
              )}
              {estimating && (
                <span className="inline-flex items-center gap-1 rounded-sm border border-action/30 bg-action/10 px-1.5 py-0.5 text-[10px] font-mono font-medium text-action">
                  <Loader2 size={10} className="animate-spin" /> Estimating
                </span>
              )}
            </div>
            <p className="text-sm text-concrete">
              {founder?.name ?? opportunity.founder_id}
              {screeningProfile?.institution_or_program ? ` · ${screeningProfile.institution_or_program}` : ""}
              {screeningProfile?.cohort_year ? ` · ${screeningProfile.cohort_year}` : ""}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {founder?.linkedin_url && (
                <SocialLink href={founder.linkedin_url} icon={Linkedin} label="LinkedIn" />
              )}
              {founder?.github_url && (
                <SocialLink href={founder.github_url} icon={Github} label="GitHub" />
              )}
              {screeningProfile?.website_url && (
                <SocialLink href={screeningProfile.website_url} icon={ArrowLeft} label="Website" />
              )}
            </div>
          </div>
          <CaseStatusBadge status={(opportunity.status as CaseStatus) || "SCREENING"} />
        </div>

        {/* Score strip — first thing visible */}
        <FourScoreStrip profile={screeningProfile} />

        <div className="flex items-center gap-3 border-t border-concrete/10 pt-3 text-sm text-concrete">
          <RecommendationBadge trigger={screeningProfile?.recommendation_trigger} />
          <span>{screeningProfile?.recommended_reason || "Not evaluated"}</span>
        </div>

        {screeningProfile?.next_diligence_action && (
          <div className="rounded-sm border border-action/20 bg-action/5 p-3 text-sm text-ink/80">
            <span className="font-semibold text-ink">Next diligence action:</span>{" "}
            {screeningProfile.next_diligence_action}
          </div>
        )}
      </div>

      {/* Pipeline actions */}
      <div className="panel space-y-3">
        <h3 className="font-display text-lg font-semibold text-ink">Pipeline actions</h3>
        <CaseStatusActions
          opportunityId={opportunity.opportunity_id}
          status={(opportunity.status as CaseStatus) || "SCREENING"}
          onUpdated={onStatusUpdated}
        />
      </div>

      {/* Associate Screen — score breakdown cards */}
      {screeningProfile && (
        <div className="panel space-y-4">
          <h3 className="font-display text-lg font-semibold text-ink">Associate Screen</h3>
          <div className="grid gap-3 lg:grid-cols-2">
            <AssociateScreenCard title="Founder" score={screeningProfile.founder_score} rationale={screeningProfile.founder_score_rationale} profile={screeningProfile} />
            <AssociateScreenCard title="Vision & Product" score={screeningProfile.vision_product_score} rationale={screeningProfile.vision_product_rationale} profile={screeningProfile} />
            <AssociateScreenCard title="Differentiation" score={screeningProfile.differentiation_score} rationale={screeningProfile.differentiation_rationale} profile={screeningProfile} />
            <AssociateScreenCard title="Traction" score={screeningProfile.traction_score} rationale={screeningProfile.traction_rationale} profile={screeningProfile} />
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            <div className="rounded-sm border border-concrete/20 bg-paper p-3 text-sm text-ink/80">
              <div className="label mb-2">Provenance</div>
              <div>Source: {screeningProfile.primary_source_url || "—"}</div>
              <div>Locator: {screeningProfile.source_locator || "—"}</div>
              <div>Evaluation scope: {screeningProfile.evaluation_scope || "—"}</div>
              <div>Individual attribution confidence: {screeningProfile.individual_attribution_confidence !== undefined ? `${Math.round(screeningProfile.individual_attribution_confidence * 100)}%` : "—"}</div>
            </div>
            <div className="rounded-sm border border-concrete/20 bg-paper p-3 text-sm text-ink/80">
              <div className="label mb-2">Funding screen</div>
              <div>{screeningProfile.funding_status.replace(/_/g, " ")}</div>
              <div>As of {screeningProfile.funding_check_as_of || "—"}</div>
              <div>Confidence {screeningProfile.funding_check_confidence !== undefined ? `${Math.round(screeningProfile.funding_check_confidence * 100)}%` : "—"}</div>
              <div className="mt-2">{screeningProfile.funding_notes || "No funding notes available."}</div>
            </div>
          </div>
        </div>
      )}

      {/* Source signal */}
      <div className="panel space-y-2">
        <h3 className="font-display text-lg font-semibold text-ink">Source signal</h3>
        <p className="text-sm font-medium text-ink">
          {founder?.source_reason || screeningProfile?.project_summary || "No summary available."}
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

      {/* Diligence claims */}
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
    </div>
  );
}
