import { ChevronDown, AlertTriangle, Minus, CheckCircle2 } from "lucide-react";
import { useState } from "react";
import type { DimensionBreakdown } from "@/types";

interface Props {
  breakdown: DimensionBreakdown;
}

const dimensionLabels: Record<string, string> = {
  execution: "Execution & shipping",
  learning: "Learning agility",
  customer_selling: "Customer & selling",
  judgment: "Judgment & prioritization",
  leadership: "Leadership & leverage",
  ownership: "Ownership & resilience",
  claim_reliability: "Claim reliability",
};

export default function DimensionRow({ breakdown }: Props) {
  const [open, setOpen] = useState(false);
  const label = dimensionLabels[breakdown.dimension] || breakdown.dimension;

  if (breakdown.unknown) {
    return (
      <div className="flex items-center justify-between rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4">
        <div className="flex items-center gap-3">
          <Minus className="text-missing" size={18} />
          <span className="font-medium text-slate-700">{label}</span>
        </div>
        <span className="rounded-full bg-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-600">Unknown</span>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between p-4 text-left hover:bg-slate-50"
      >
        <div className="flex items-center gap-4">
          <span className="min-w-[180px] font-medium text-ink">{label}</span>
          <span className="text-2xl font-bold tabular text-ink">{breakdown.adjusted_score}</span>
          <span className="text-xs text-slate-500">
            raw {breakdown.raw_score} · {Math.round(breakdown.confidence * 100)}% conf ·{" "}
            {breakdown.evidence_count} items
          </span>
          {breakdown.contradiction_count > 0 && (
            <span className="flex items-center gap-1 rounded bg-red-50 px-2 py-0.5 text-xs font-semibold text-contradiction">
              <AlertTriangle size={12} /> {breakdown.contradiction_count} contradiction
            </span>
          )}
        </div>
        <ChevronDown size={18} className={`transform text-slate-400 transition ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="border-t border-slate-100 px-4 pb-4 pt-3">
          <div className="mb-3 flex items-center gap-6 text-sm text-slate-600">
            <span>Weight {Math.round(breakdown.weight * 100)}%</span>
            <span>Band {breakdown.evidence_band_low}–{breakdown.evidence_band_high}</span>
            <span>Coverage {Math.round(breakdown.coverage * 100)}%</span>
          </div>

          {breakdown.positive_evidence.length > 0 && (
            <div className="mb-3">
              <div className="label mb-1.5">Supporting evidence</div>
              <ul className="space-y-1.5">
                {breakdown.positive_evidence.map((ev, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                    <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-verified" />
                    {ev}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {breakdown.counter_evidence.length > 0 && (
            <div className="mb-3">
              <div className="label mb-1.5 text-contradiction">Counter evidence</div>
              <ul className="space-y-1.5">
                {breakdown.counter_evidence.map((ev, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-contradiction">
                    <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                    {ev}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {breakdown.unknowns.length > 0 && (
            <div>
              <div className="label mb-1.5">Unknowns</div>
              <ul className="space-y-1 text-sm text-slate-600">
                {breakdown.unknowns.map((u, i) => (
                  <li key={i}>• {u}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
