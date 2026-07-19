import { useEffect, useState } from "react";
import { Loader2, ChevronRight, Gavel, XCircle, Eye, HelpCircle } from "lucide-react";
import { api } from "@/api/client";
import type { ApiError, BackendOpportunity } from "@/types/backend";
import type { CaseStatus } from "@/domain/types";
import { allowedTransitions, nextStatusAfterDecision } from "@/engine/routing";
import { canDecide, statusLabel } from "@/engine/stateMachine";

type Decision = "INVEST" | "DECLINE" | "MONITOR" | "REQUEST_EVIDENCE";

const DECISIONS: { key: Decision; label: string; icon: typeof Gavel; className: string }[] = [
  {
    key: "INVEST",
    label: "Invest",
    icon: Gavel,
    className: "border-verified/30 bg-verified/10 text-verified hover:bg-verified/20",
  },
  {
    key: "DECLINE",
    label: "Decline",
    icon: XCircle,
    className: "border-contradiction/30 bg-contradiction/10 text-contradiction hover:bg-contradiction/20",
  },
  {
    key: "MONITOR",
    label: "Monitor",
    icon: Eye,
    className: "border-uncertain/30 bg-uncertain/10 text-uncertain hover:bg-uncertain/20",
  },
  {
    key: "REQUEST_EVIDENCE",
    label: "Request evidence",
    icon: HelpCircle,
    className: "border-action/30 bg-action/10 text-action hover:bg-action/20",
  },
];

export function CaseStatusActions({
  opportunityId,
  status,
  onUpdated,
}: {
  opportunityId: string;
  status: CaseStatus;
  onUpdated?: (opp: BackendOpportunity) => void;
}) {
  const [selected, setSelected] = useState<CaseStatus>(status);
  const [loadingKey, setLoadingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSelected(status);
  }, [status]);

  const apply = async (next: CaseStatus, key: string) => {
    setLoadingKey(key);
    setError(null);
    try {
      const updated = await api.opportunities.updateStatus(opportunityId, next);
      setSelected(updated.status as CaseStatus);
      onUpdated?.(updated);
    } catch (err) {
      setError((err as ApiError).message || "Failed to update status");
    } finally {
      setLoadingKey(null);
    }
  };

  const transitions = allowedTransitions(status);
  const showDecisionQueue = status !== "PARTNER_REVIEW";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {showDecisionQueue && (
          <button
            onClick={() => apply("PARTNER_REVIEW", "queue")}
            disabled={!!loadingKey}
            className="flex items-center gap-2 rounded-sm bg-action px-3 py-1.5 text-sm font-sans font-medium text-paper hover:bg-action-dark disabled:opacity-50"
          >
            {loadingKey === "queue" ? <Loader2 size={14} className="animate-spin" /> : <ChevronRight size={14} />}
            Move to decision queue
          </button>
        )}

        {canDecide(status) &&
          DECISIONS.map((d) => {
            const Icon = d.icon;
            const next = nextStatusAfterDecision(d.key, status);
            return (
              <button
                key={d.key}
                onClick={() => apply(next, `decision-${d.key}`)}
                disabled={!!loadingKey}
                className={`flex items-center gap-1.5 rounded-sm border px-3 py-1.5 text-sm font-sans font-medium disabled:opacity-50 ${d.className}`}
              >
                {loadingKey === `decision-${d.key}` ? <Loader2 size={14} className="animate-spin" /> : <Icon size={14} />}
                {d.label}
              </button>
            );
          })}
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <div>
          <div className="label mb-1.5">Update status</div>
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value as CaseStatus)}
            className="rounded-sm border border-concrete/30 bg-paper px-2 py-1.5 text-sm font-sans outline-none"
          >
            {transitions.map((s) => (
              <option key={s} value={s}>
                {statusLabel(s)}
              </option>
            ))}
          </select>
        </div>
        <button
          onClick={() => selected !== status && apply(selected, "select")}
          disabled={!!loadingKey || selected === status}
          className="flex items-center gap-1.5 rounded-sm border border-concrete/30 bg-paper px-3 py-1.5 text-sm font-sans font-medium text-ink hover:bg-manila/40 disabled:opacity-50"
        >
          {loadingKey === "select" ? <Loader2 size={14} className="animate-spin" /> : <ChevronRight size={14} />}
          Apply
        </button>
      </div>

      {error && (
        <div className="rounded-sm border border-contradiction/20 bg-contradiction/10 p-2 text-sm text-contradiction">
          {error}
        </div>
      )}
    </div>
  );
}
