import { DEFAULT_THESIS, THESIS_DESCRIPTION, parseThesisQuery, DEFAULT_CHECK_SIZE, DEFAULT_OWNERSHIP_TARGET } from "@/config/thesis";
import { useEffect, useMemo, useState } from "react";
import { useApp } from "@/store/appContext";
import { Loader2, CheckCircle2, AlertCircle, Plus } from "lucide-react";
import type { ThesisConfig } from "@/domain/types";
import type { BackendThesis } from "@/types/backend";

export default function Thesis() {
  const { state, activeThesis, setActiveThesis, createThesis } = useApp();
  const [query, setQuery] = useState(THESIS_DESCRIPTION);
  const parsed = parseThesisQuery(query);

  const [isCreating, setIsCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    sectors: "",
    stages: "",
    geographies: "",
    check_size_min: "",
    check_size_max: "",
    risk_appetite: "moderate",
  });

  useEffect(() => {
    if (activeThesis) {
      setForm({
        name: activeThesis.name,
        sectors: activeThesis.sectors.join(", "),
        stages: activeThesis.stages.join(", "),
        geographies: activeThesis.geographies.join(", "),
        check_size_min: activeThesis.check_size_min.toString(),
        check_size_max: activeThesis.check_size_max.toString(),
        risk_appetite: activeThesis.risk_appetite,
      });
    }
  }, [activeThesis?.id]);

  const activeThesisConfig: ThesisConfig = useMemo(
    () => (activeThesis ? mapBackendThesis(activeThesis) : DEFAULT_THESIS),
    [activeThesis]
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setIsCreating(true);

    const checkMin = Number(form.check_size_min) || 0;
    const checkMax = Number(form.check_size_max) || 1_000_000;

    if (!form.name.trim()) {
      setFormError("Name is required.");
      setIsCreating(false);
      return;
    }

    try {
      await createThesis({
        name: form.name.trim(),
        sectors: splitList(form.sectors),
        stages: splitList(form.stages),
        geographies: splitList(form.geographies),
        check_size_min: checkMin,
        check_size_max: Math.max(checkMin, checkMax),
        risk_appetite: form.risk_appetite,
      });
      setForm({
        name: "",
        sectors: "",
        stages: "",
        geographies: "",
        check_size_min: "",
        check_size_max: "",
        risk_appetite: "moderate",
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to save thesis";
      setFormError(message);
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <div className="label mb-1">Thesis configuration</div>
          <h1 className="text-2xl font-bold text-ink">Investment mandate</h1>
          <p className="text-sm text-concrete">Sector, stage, geography, check size, ownership, and exclusions.</p>
        </div>
        <div>{state.thesisLoading && <Loader2 size={16} className="animate-spin text-concrete" />}</div>
      </div>

      {activeThesis && (
        <div className="rounded-sm border border-verified/20 bg-verified/5 p-3 text-sm text-ink">
          <span className="rounded-sm bg-verified/10 px-1.5 py-0.5 text-[10px] font-mono font-semibold uppercase text-verified">
            Live
          </span>{" "}
          Using backend thesis: {activeThesis.name}
        </div>
      )}

      {state.thesisError && !activeThesis && (
        <div className="rounded-sm border border-contradiction/20 bg-contradiction/10 p-3 text-sm text-contradiction">
          <AlertCircle size={16} className="inline mr-1" />
          {state.thesisError}
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="panel space-y-4">
          <h3 className="font-display text-lg font-semibold text-ink">Settings</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Sector" value={activeThesisConfig.sector.join(", ")} />
            <Field label="Stage" value={activeThesisConfig.stage.join(", ")} />
            <Field label="Geography" value={activeThesisConfig.geography.join(", ")} />
            <Field label="Check size" value={`$${activeThesisConfig.checkSize.toLocaleString()}`} />
            <Field label="Ownership target" value={`${(activeThesisConfig.ownershipTarget * 100).toFixed(1)}%`} />
            <Field label="Risk appetite" value={activeThesisConfig.riskAppetite} />
          </div>
          <div>
            <div className="label mb-1.5">Exclusions</div>
            <ul className="list-inside list-disc text-sm text-ink/80">
              {activeThesisConfig.exclusions.map((e) => (
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

      {/* Manual thesis form */}
      <div className="panel space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-display text-lg font-semibold text-ink">Manual thesis</h3>
          {activeThesis && (
            <span className="text-xs text-concrete">
              Editing from: <span className="font-medium text-ink">{activeThesis.name}</span>
            </span>
          )}
        </div>
        <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Input label="Name" value={form.name} onChange={(v) => setForm((f) => ({ ...f, name: v }))} placeholder="e.g. Early-stage B2B SaaS" required />
          <Input label="Sectors" value={form.sectors} onChange={(v) => setForm((f) => ({ ...f, sectors: v }))} placeholder="comma-separated" />
          <Input label="Stages" value={form.stages} onChange={(v) => setForm((f) => ({ ...f, stages: v }))} placeholder="comma-separated" />
          <Input label="Geographies" value={form.geographies} onChange={(v) => setForm((f) => ({ ...f, geographies: v }))} placeholder="comma-separated" />
          <Input label="Check size min" value={form.check_size_min} onChange={(v) => setForm((f) => ({ ...f, check_size_min: v }))} placeholder="0" type="number" />
          <Input label="Check size max" value={form.check_size_max} onChange={(v) => setForm((f) => ({ ...f, check_size_max: v }))} placeholder="1000000" type="number" />
          <div className="md:col-span-2">
            <div className="label mb-1.5">Risk appetite</div>
            <select
              className="w-full rounded-sm border border-concrete/30 bg-paper px-3 py-2 text-sm font-sans outline-none"
              value={form.risk_appetite}
              onChange={(e) => setForm((f) => ({ ...f, risk_appetite: e.target.value }))}
            >
              <option value="conservative">Conservative</option>
              <option value="moderate">Moderate</option>
              <option value="aggressive">Aggressive</option>
            </select>
          </div>
          {formError && (
            <div className="md:col-span-2 rounded-sm border border-contradiction/20 bg-contradiction/10 p-2 text-sm text-contradiction">
              {formError}
            </div>
          )}
          <div className="md:col-span-2">
            <button
              type="submit"
              disabled={isCreating}
              className="flex items-center gap-2 rounded-sm bg-action px-4 py-2 text-sm font-sans font-medium text-paper hover:bg-action-dark disabled:opacity-50"
            >
              {isCreating ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
              Save thesis to database
            </button>
          </div>
        </form>
      </div>

      {/* Existing theses selector */}
      {state.theses.length > 0 && (
        <div className="panel space-y-4">
          <h3 className="font-display text-lg font-semibold text-ink">Stored theses</h3>
          <div className="space-y-2">
            {state.theses.map((t) => (
              <button
                key={t.id}
                onClick={() => setActiveThesis(t.id)}
                className={`flex w-full items-center justify-between rounded-sm border px-4 py-3 text-left transition-colors ${
                  activeThesis?.id === t.id
                    ? "border-verified/30 bg-verified/5"
                    : "border-concrete/20 bg-paper hover:bg-manila/30"
                }`}
              >
                <div>
                  <div className="font-sans font-semibold text-ink">{t.name}</div>
                  <div className="text-xs text-concrete">
                    {t.sectors.join(", ")} · {t.stages.join(", ")} · {t.geographies.join(", ")}
                  </div>
                </div>
                {activeThesis?.id === t.id && (
                  <span className="flex items-center gap-1 text-xs font-medium text-verified">
                    <CheckCircle2 size={14} /> Active
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}
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

function Input({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
  required,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: string;
  required?: boolean;
}) {
  return (
    <div>
      <div className="label mb-1.5">{label}</div>
      <input
        type={type}
        required={required}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-sm border border-concrete/30 bg-paper px-3 py-2 text-sm font-sans outline-none"
      />
    </div>
  );
}

function splitList(raw: string): string[] {
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
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
