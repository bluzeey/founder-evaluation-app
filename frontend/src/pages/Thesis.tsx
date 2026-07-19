import { DEFAULT_THESIS, THESIS_DESCRIPTION, isWithinThesis, parseThesisQuery, DEFAULT_CHECK_SIZE } from "@/config/thesis";
import { DEMO_CASES, getDemoCompany } from "@/data/demoCases";
import { DemoBadge } from "@/components/DemoBadge";
import { useState } from "react";

export default function Thesis() {
  const thesis = DEFAULT_THESIS;
  const [query, setQuery] = useState(THESIS_DESCRIPTION);
  const parsed = parseThesisQuery(query);

  const results = DEMO_CASES.map((c) => {
    const company = c.companyId ? getDemoCompany(c.companyId) : undefined;
    if (!company) return null;
    const match = isWithinThesis(company.sector, company.stage, company.geography, thesis);
    return { caseId: c.id, company, match, checkSize: thesis.checkSize };
  }).filter(Boolean);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <div className="label mb-1">Thesis configuration</div>
          <h1 className="text-2xl font-bold text-ink">Investment mandate</h1>
          <p className="text-sm text-concrete">Sector, stage, geography, check size, ownership, and exclusions.</p>
        </div>
        <DemoBadge />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="panel space-y-4">
          <h3 className="font-display text-lg font-semibold text-ink">Settings</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Sector" value={thesis.sector.join(", ")} />
            <Field label="Stage" value={thesis.stage.join(", ")} />
            <Field label="Geography" value={thesis.geography.join(", ")} />
            <Field label="Check size" value={`$${thesis.checkSize.toLocaleString()}`} />
            <Field label="Ownership target" value={`${(thesis.ownershipTarget * 100).toFixed(1)}%`} />
            <Field label="Risk appetite" value={thesis.riskAppetite} />
          </div>
          <div>
            <div className="label mb-1.5">Exclusions</div>
            <ul className="list-inside list-disc text-sm text-ink/80">
              {thesis.exclusions.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </div>
          <div className="text-xs text-concrete">
            Default check size is $100,000. Target one investment decision every 4–5 days.
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
            <div className="mt-2 text-xs text-concrete">
              Keywords: {parsed.keywords.join(", ")}
            </div>
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
