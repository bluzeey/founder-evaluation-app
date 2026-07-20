import { useNavigate } from "react-router-dom";
import { Loader2, Search } from "lucide-react";
import { FourScoreStrip, scoreValue } from "@/features/founders/FourScoreStrip";
import { RecommendationBadge } from "@/features/founders/RecommendationBadge";
import { useFounderDiscovery } from "@/features/founders/useFounderDiscovery";
import type { BackendFounderDiscoveryItem, BackendFounderScreeningProfile } from "@/types/backend";

type FounderListPageProps = {
  title: string;
  description: string;
  recommendedOnly?: boolean;
  ruleExplanation?: string;
};

function percent(value?: number | null) {
  return value === null || value === undefined ? "—" : `${Math.round(value * 100)}%`;
}

function fundingLabel(profile?: BackendFounderScreeningProfile | null) {
  const value = profile?.funding_status ?? "unknown";
  return value.replace(/_/g, " ");
}

export function FounderListPage({
  title,
  description,
  recommendedOnly = false,
  ruleExplanation,
}: FounderListPageProps) {
  const navigate = useNavigate();
  const { page, loading, error, params, searchInput, setSearchInput, updateParam, goToOffset } =
    useFounderDiscovery({ recommendedOnly });

  const items = page?.items ?? [];
  const offset = page?.offset ?? 0;
  const limit = page?.limit ?? 50;
  const hasPrevious = offset > 0;
  const hasNext = page ? offset + limit < page.total : false;

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <div className="label">Founders</div>
        <h1 className="text-2xl font-bold text-ink">{title}</h1>
        <p className="max-w-3xl text-sm text-concrete">{description}</p>
        {ruleExplanation && (
          <div className="rounded-sm border border-action/20 bg-action/5 p-3 text-sm text-ink/80">
            {ruleExplanation}
          </div>
        )}
      </div>

      <div className="space-y-3 rounded-sm border border-concrete/20 bg-manila/20 p-3 shadow-paper">
        <div className="flex min-w-[180px] max-w-md items-center gap-2 rounded-sm border border-concrete/30 bg-paper px-2 py-1.5">
          <Search size={14} className="text-concrete" />
          <input
            className="min-w-0 flex-1 bg-transparent text-sm font-sans outline-none"
            placeholder="Search founder, project, role, summary, or tags"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
          />
        </div>

        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-7">
          {!recommendedOnly && (
            <FilterSelect
              label="Recommended"
              value={String(params.recommended ?? "")}
              onChange={(value) => updateParam("recommended", value || null)}
              options={[
                { value: "", label: "All" },
                { value: "true", label: "Recommended" },
                { value: "false", label: "Not recommended" },
              ]}
            />
          )}
          <FilterSelect
            label="City"
            value={String(params.city ?? "")}
            onChange={(value) => updateParam("city", value || null)}
            options={[{ value: "", label: "All" }, ...(page?.facets.cities ?? []).map((value) => ({ value, label: value }))]}
          />
          <FilterSelect
            label="Institution/program"
            value={String(params.institution_or_program ?? "")}
            onChange={(value) => updateParam("institution_or_program", value || null)}
            options={[
              { value: "", label: "All" },
              ...(page?.facets.institutions_or_programs ?? []).map((value) => ({ value, label: value })),
            ]}
          />
          <FilterSelect
            label="School/lab"
            value={String(params.school_or_lab ?? "")}
            onChange={(value) => updateParam("school_or_lab", value || null)}
            options={[{ value: "", label: "All" }, ...(page?.facets.schools_or_labs ?? []).map((value) => ({ value, label: value }))]}
          />
          <FilterSelect
            label="Source type"
            value={String(params.source_type ?? "")}
            onChange={(value) => updateParam("source_type", value || null)}
            options={[{ value: "", label: "All" }, ...(page?.facets.source_types ?? []).map((value) => ({ value, label: value }))]}
          />
          <FilterSelect
            label="Sector"
            value={String(params.sector ?? "")}
            onChange={(value) => updateParam("sector", value || null)}
            options={[{ value: "", label: "All" }, ...(page?.facets.sectors ?? []).map((value) => ({ value, label: value }))]}
          />
          <FilterSelect
            label="Funding"
            value={String(params.funding_status ?? "")}
            onChange={(value) => updateParam("funding_status", value || null)}
            options={[
              { value: "", label: "All" },
              ...(page?.facets.funding_statuses ?? []).map((value) => ({ value, label: value.replace(/_/g, " ") })),
            ]}
          />
        </div>
      </div>

      <div className="flex items-center justify-between text-sm text-concrete">
        <div className="flex items-center gap-2">
          <span className="font-display font-semibold text-ink">{page?.total ?? 0}</span> founders
          {loading && <Loader2 size={14} className="animate-spin text-concrete" />}
        </div>
      </div>

      {error ? (
        <div className="rounded-sm border border-contradiction/20 bg-contradiction/10 p-3 text-sm text-contradiction">
          {error}
        </div>
      ) : items.length === 0 && !loading ? (
        <div className="panel py-10 text-center text-concrete">No founders match the current filters.</div>
      ) : (
        <div className="overflow-x-auto rounded-sm border border-concrete/20 bg-paper shadow-paper">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-concrete/20 bg-manila/30">
              <tr>
                <th className="px-4 py-3 font-semibold text-ink">Founder and project</th>
                <th className="px-4 py-3 font-semibold text-ink">Institution/program</th>
                <th className="px-4 py-3 font-semibold text-ink">City</th>
                <th className="hidden px-4 py-3 font-semibold text-ink xl:table-cell">Founder</th>
                <th className="hidden px-4 py-3 font-semibold text-ink xl:table-cell">Vision &amp; Product</th>
                <th className="hidden px-4 py-3 font-semibold text-ink xl:table-cell">Differentiation</th>
                <th className="hidden px-4 py-3 font-semibold text-ink xl:table-cell">Traction</th>
                <th className="px-4 py-3 font-semibold text-ink">Recommendation</th>
                <th className="px-4 py-3 font-semibold text-ink">Evidence</th>
                <th className="px-4 py-3 font-semibold text-ink">Funding screen</th>
                <th className="px-4 py-3 font-semibold text-ink">Next diligence action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-concrete/10">
              {items.map((item) => (
                <FounderRow key={item.founder.id} item={item} onOpen={() => item.opportunity && navigate(`/cases/${item.opportunity.opportunity_id}`)} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-end gap-2">
        <button
          className="rounded-sm border border-concrete/30 bg-paper px-3 py-1.5 text-sm disabled:opacity-50"
          disabled={!hasPrevious}
          onClick={() => goToOffset(offset - limit)}
        >
          Previous
        </button>
        <button
          className="rounded-sm border border-concrete/30 bg-paper px-3 py-1.5 text-sm disabled:opacity-50"
          disabled={!hasNext}
          onClick={() => goToOffset(offset + limit)}
        >
          Next
        </button>
      </div>
    </div>
  );
}

function FounderRow({ item, onOpen }: { item: BackendFounderDiscoveryItem; onOpen: () => void }) {
  const profile = item.profile;
  const clickable = Boolean(item.opportunity);
  return (
    <tr
      onClick={clickable ? onOpen : undefined}
      className={clickable ? "cursor-pointer transition-colors hover:bg-manila/20" : ""}
    >
      <td className="px-4 py-3 align-top">
        <div className="space-y-2">
          <div>
            <div className="font-sans font-semibold text-ink">{item.founder.name}</div>
            <div className="text-xs text-concrete">
              {profile?.project_name || item.founder.current_company || "—"} · {profile?.founder_role || item.founder.role || "—"}
            </div>
          </div>
          <div className="xl:hidden">
            <FourScoreStrip profile={profile} />
          </div>
        </div>
      </td>
      <td className="px-4 py-3 align-top">
        <div className="font-medium text-ink">{profile?.institution_or_program || "—"}</div>
        <div className="text-xs text-concrete">{profile?.cohort_year || "—"} · {profile?.school_or_lab || "—"}</div>
      </td>
      <td className="px-4 py-3 align-top">
        <div className="font-medium text-ink">{profile?.city || "—"}</div>
        <div className="text-xs text-concrete">
          {profile?.city_basis || "basis unavailable"} · confidence {percent(profile?.city_confidence)}
        </div>
      </td>
      <td className="hidden px-4 py-3 align-top xl:table-cell">{scoreValue(profile, "founder_score")}</td>
      <td className="hidden px-4 py-3 align-top xl:table-cell">{scoreValue(profile, "vision_product_score")}</td>
      <td className="hidden px-4 py-3 align-top xl:table-cell">{scoreValue(profile, "differentiation_score")}</td>
      <td className="hidden px-4 py-3 align-top xl:table-cell">{scoreValue(profile, "traction_score")}</td>
      <td className="px-4 py-3 align-top">
        <div className="space-y-2">
          <RecommendationBadge trigger={profile?.recommendation_trigger} />
          <div className="text-xs text-concrete">{profile?.recommended_reason || "Not evaluated"}</div>
        </div>
      </td>
      <td className="px-4 py-3 align-top text-xs text-concrete">
        Confidence {percent(profile?.evidence_confidence)}
        <br />
        Coverage {percent(profile?.evidence_coverage)}
      </td>
      <td className="px-4 py-3 align-top text-xs text-concrete">
        <div className="font-medium text-ink/90">{fundingLabel(profile)}</div>
        <div>As of {profile?.funding_check_as_of || "—"}</div>
      </td>
      <td className="px-4 py-3 align-top text-xs text-ink/80">{profile?.next_diligence_action || "—"}</td>
    </tr>
  );
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <label className="space-y-1 text-xs text-concrete">
      <span className="label">{label}</span>
      <select
        className="w-full rounded-sm border border-concrete/30 bg-paper px-2 py-1.5 text-sm text-ink outline-none"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={`${label}-${option.value}`} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
