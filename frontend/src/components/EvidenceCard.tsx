import { CheckCircle2, HelpCircle, AlertTriangle, Minus, BrainCircuit } from "lucide-react";
import type { EvidenceItem } from "@/types";

interface Props {
  evidence: EvidenceItem;
}

const statusConfig: Record<string, { icon: typeof CheckCircle2; color: string; label: string }> = {
  positive: { icon: CheckCircle2, color: "text-verified", label: "Positive" },
  negative: { icon: AlertTriangle, color: "text-contradiction", label: "Negative" },
  contradictory: { icon: AlertTriangle, color: "text-contradiction", label: "Contradictory" },
  mixed: { icon: HelpCircle, color: "text-uncertain", label: "Mixed" },
  unknown: { icon: Minus, color: "text-missing", label: "Unknown" },
};

export default function EvidenceCard({ evidence }: Props) {
  const config = statusConfig[evidence.status] || statusConfig.unknown;
  const Icon = config.icon;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Icon size={16} className={config.color} />
          <span className={`text-xs font-bold uppercase ${config.color}`}>{config.label}</span>
        </div>
        <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
          {evidence.evidence_type.replace(/_/g, " ")}
        </span>
      </div>
      <p className="mb-3 text-sm font-medium text-ink">{evidence.observation}</p>
      <div className="grid grid-cols-2 gap-2 text-xs text-slate-500">
        <span>Source: {evidence.source_type}</span>
        <span>Locator: {evidence.source_locator}</span>
        <span>Rubric level: {evidence.rubric_level}/4</span>
        <span>Independence: {evidence.independence_group}</span>
      </div>
      {evidence.unknowns && (
        <div className="mt-3 flex items-start gap-2 rounded bg-slate-50 p-2 text-xs text-slate-600">
          <BrainCircuit size={14} className="mt-0.5 shrink-0 text-inferred" />
          {evidence.unknowns}
        </div>
      )}
    </div>
  );
}
