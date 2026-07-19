import { DEFAULT_THESIS, THESIS_DESCRIPTION, isWithinThesis, parseThesisQuery, DEFAULT_CHECK_SIZE, DEFAULT_OWNERSHIP_TARGET } from "@/config/thesis";
import { DEMO_CASES, getDemoCompany } from "@/data/demoCases";
import { DemoBadge } from "@/components/DemoBadge";
import { useEffect, useState } from "react";
import { api } from "@/api/client";
import { Loader2 } from "lucide-react";
import type { ThesisConfig } from "@/domain/types";
import type { BackendThesis } from "@/types/backend";

export default function Thesis() {
  const [backendTheses, setBackendTheses] = useState<BackendThesis[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState(THESIS_DESCRIPTION);
  const parsed = parseThesisQuery(query);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.theses
      .list()
      .then((theses) => {
        if (!cancelled) setBackendTheses(theses);
      })
      .catch(() => {
        // Backend thesis is optional; fall back to default thesis.
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const activeThesis: ThesisConfig = backendTheses.length > 0 ? mapBackendThesis(backendTheses[0]) : DEFAULT_THESIS;
  const checkSize = activeThesis.checkSize;

  const results = DEMO_CASES.map((c) => {
    const company = c.companyId ? getDemoCompany(c.companyId) : undefined;
    if (!company) return null;
    const match = isWithinThesis(company.sector, company.stage, company.geography, activeThesis);
    return { caseId: c.id, company, match, checkSize };
  }).filter(Boolean);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <div className="label mb-1">Thesis configuration</div>
          <h1 className="text-2xl font-bold text-ink">Investment mandate</h1>
          <p className="text-sm text-concrete">Sector, stage, geography, check size, ownership, and exclusions.</p>
        </div>
        <div className="flex items-center gap-2">
          <DemoBadge />
          {loading && <Loader2 size={16} className="animate-spin text-concrete" />}
        </div>
      </div>

      {backendTheses.length > 0 && (
        <div className="rounded-sm border border-verified/20 bg-verified/5 p-3 text-sm text-ink">
          <span className="rounded-sm bg-verified/10 px-1.5 py-0.5 text-[10px] font-mono font-semibold uppercase text-verified">
            Live
          </span>{" "}
          Using backend thesis: {backendTheses[0].name}
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="panel space-y-4">
          <h3 className="font-display text-lg font-semibold text-ink">Settings</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Sector" value={activeThesis.sector.join(", ")} />
            <Field label="Stage" value={activeThesis.stage.join(", ")} />
            <Field label="Geography" value={activeThesis.geography.join(", ")} />
            <Field label="Check size" value={`$${activeThesis.checkSize.toLocaleString()}`} />
            <Field label="Ownership target" value={`${(activeThesis.ownershipTarget * 100).toFixed(1)}%`} />
            <Field label="Risk appetite" value={activeThesis.riskAppetite} />
          </div>
          <div>
            <div className="label mb-1.5">Exclusions</div>
            <ul className="list-inside list-disc text-sm text-ink/80">
              {activeThesis.exclusions.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </div>
          <div className="text-xs text-concrete">
            Default check size is ${DEFAULT_CHECK_SIZE.toLocaleString()}. Target one investment decision every 4–5 days.
          </div>
        </div>

        <div className="panel space-y-4">
          <h3 className="font-display text-lg font-semibold text-ink">Compound query</h3>
          <textarea
            className="h-24 w-full rounded-sm border border-concrete/30 bg-paper p-3 text-sm font-sans outline-none"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="rounded-sm border border-concrete/20 bg-manila/30 p-3">
            <div className="label">Parsed filters</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {parsed.sector?.map((s) => <Badge key={s} text={s} />)}
              {parsed.stage?.map((s) => <Badge key={s} text={s} />)}
              {parsed.geography?.map((s) => <Badge key={s} text={s} />)}
              <Badge text={`$${(parsed.checkSize ?? DEFAULT_CHECK_SIZE).toLocaleString()}`} />
              <Badge text={parsed.riskAppetite ?? "MODERATE"} />
            </div>
            <div className="mt-2 text-xs text-concrete">Keywords: {parsed.keywords.join(", ")}</div>
          </div>
          <div className="text-xs text-concrete">
            This is keyword-based parsing with transparent filters, not model reasoning presented as inference.
          </div>
        </div>
      </div>

      <div className="panel space-y-4">
        <h3 className="font-display text-lg font-semibold text-ink">Query results</h3>
        <div className="space-y-3">
          {results.map((r) =>
            r ? (
              <div
                key={r.caseId}
                className={`flex items-center justify-between rounded-sm border p-3 ${
                  r.match.eligible ? "border-verified/30 bg-verified/10" : "border-concrete/20 bg-paper"
                }`}
              >
                <div>
                  <div className="font-sans font-semibold text-ink">
                    {r.company.name} · {r.company.sector} · {r.company.stage} · {r.company.geography}
                  </div>
                  <div className="text-xs text-concrete">
                    Matches: {r.match.matches.join(", ") || "none"} · Mismatches: {r.match.mismatches.join(", ") || "none"}
                  </div>
                </div>
                <div className="text-right">
                  <div className={`text-sm font-semibold ${r.match.eligible ? "text-verified" : "text-concrete"}`}>
                    {r.match.eligible ? "Eligible" : "Ineligible"}
                  </div>
                  <div className="text-xs text-concrete">Check ${r.checkSize.toLocaleString()}</div>
                </div>
              </div>
            ) : null
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="label">{label}</div>
      <div className="text-sm font-medium text-ink">{value}</div>
    </div>
  );
}

function Badge({ text }: { text: string }) {
  return (
    <span className="rounded-sm border border-concrete/20 bg-paper px-2 py-0.5 text-xs font-mono font-medium text-ink">
      {text}
    </span>
  );
}

function mapBackendThesis(t: BackendThesis): ThesisConfig {
  const riskAppetite = t.risk_appetite.toUpperCase();
  return {
    sector: t.sectors,
    stage: t.stages,
    geography: t.geographies,
    checkSize: t.check_size_max,
    ownershipTarget: DEFAULT_OWNERSHIP_TARGET,
    riskAppetite: riskAppetite === "CONSERVATIVE" || riskAppetite === "MODERATE" || riskAppetite === "AGGRESSIVE" ? riskAppetite : "MODERATE",
    exclusions: DEFAULT_THESIS.exclusions,
  };
}
