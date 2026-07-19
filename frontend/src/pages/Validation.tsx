import { useEffect, useState } from "react";
import { CheckCircle2, XCircle, AlertTriangle } from "lucide-react";
import { computeValidationSummary, ValidationSummary } from "@/engine/validationSummary";

export default function Validation() {
  const [summary, setSummary] = useState<ValidationSummary | null>(null);
  useEffect(() => {
    setSummary(computeValidationSummary());
  }, []);

  if (!summary) return <div className="panel py-12 text-center">Computing validation summary…</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <div className="label mb-1">Validation summary</div>
          <h1 className="text-2xl font-bold text-ink">System audit</h1>
          <p className="text-sm text-concrete">Deterministic checks over engine output.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <MetricCard
          label="Citation coverage"
          value={`${summary.citationCoverage}%`}
          ok={summary.citationCoverage >= 80}
        />
        <MetricCard
          label="Seeded contradictions detected"
          value={summary.contradictionsDetected.toString()}
          ok={summary.contradictionsDetected > 0}
        />
        <MetricCard
          label="Unsupported numeric claims"
          value={summary.unsupportedNumericClaims.toString()}
          ok={summary.unsupportedNumericClaims === 0}
        />
        <MetricCard
          label="Routing tests"
          value={`${summary.routingTestsPassed}/${summary.routingTestsTotal}`}
          ok={summary.routingTestsPassed === summary.routingTestsTotal}
        />
        <MetricCard
          label="Avg processing time"
          value={`${summary.averageProcessingTimeMs} ms`}
          ok={summary.averageProcessingTimeMs < 1000}
        />
        <MetricCard
          label="Human overrides"
          value={summary.humanOverrideCount.toString()}
          ok={true}
        />
      </div>

      <div className="panel space-y-3">
        <h3 className="font-display text-lg font-semibold text-ink">Details</h3>
        {summary.details.length === 0 ? (
          <div className="flex items-center gap-2 text-sm text-verified">
            <CheckCircle2 size={16} /> All deterministic checks passed.
          </div>
        ) : (
          summary.details.map((d, i) => (
            <div key={i} className="flex items-start gap-2 text-sm text-contradiction">
              <XCircle size={16} className="mt-0.5" /> {d}
            </div>
          ))
        )}
      </div>

      <div className="panel space-y-3">
        <h3 className="font-display text-lg font-semibold text-ink">24-hour processing timeline</h3>
        <div className="space-y-2">
          <Step done label="Ingestion" detail="Deck / form / web claims extracted" />
          <Step done label="Validator" detail="Contradictions and quarantines flagged" />
          <Step done label="Specialists" detail="Six driver scores and confidence assigned" />
          <Step done label="Router" detail="Status, owner, and next action set" />
          <Step done={false} label="Partner decision" detail="Pending for cases not on hold" />
        </div>
      </div>
    </div>
  );
}

function MetricCard({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className={`panel flex items-center justify-between ${ok ? "border-l-4 border-l-verified" : "border-l-4 border-l-contradiction"}`}>
      <div>
        <div className="label">{label}</div>
        <div className="font-display text-xl font-bold tabular text-ink">{value}</div>
      </div>
      {ok ? <CheckCircle2 size={24} className="text-verified" /> : <AlertTriangle size={24} className="text-contradiction" />}
    </div>
  );
}

function Step({ done, label, detail }: { done: boolean; label: string; detail: string }) {
  return (
    <div className="flex items-start gap-3">
      <div className={`mt-0.5 h-2 w-2 rounded-full ${done ? "bg-verified" : "bg-concrete/40"}`} />
      <div className="text-sm">
        <span className={`font-medium ${done ? "text-ink" : "text-concrete"}`}>{label}</span>
        <span className="text-concrete"> — {detail}</span>
      </div>
    </div>
  );
}
