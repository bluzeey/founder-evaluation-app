import type { CaseStatus, ClaimStatus } from "@/domain/types";
import { statusLabel } from "@/engine/stateMachine";

const statusStyles: Record<CaseStatus, string> = {
  DISCOVERED: "bg-slate-100 text-slate-700",
  ACTIVATION_READY: "bg-green-50 text-verified",
  AWAITING_APPLICATION: "bg-amber-50 text-uncertain",
  SCREENING: "bg-blue-50 text-action",
  DILIGENCE: "bg-amber-50 text-uncertain",
  VALIDATION_HOLD: "bg-red-50 text-contradiction",
  ASSOCIATE_REVIEW: "bg-purple-50 text-inferred",
  PARTNER_REVIEW: "bg-indigo-50 text-ink",
  INVESTED: "bg-green-100 text-verified",
  DECLINED: "bg-slate-200 text-slate-700",
  MONITORING: "bg-amber-100 text-uncertain",
};

export function CaseStatusBadge({ status }: { status: CaseStatus }) {
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${statusStyles[status]}`}>
      {statusLabel(status)}
    </span>
  );
}

const claimStyles: Record<ClaimStatus, string> = {
  DECLARED: "bg-blue-50 text-action",
  INFERRED: "bg-purple-50 text-inferred",
  VERIFIED: "bg-green-50 text-verified",
  CONTRADICTED: "bg-red-50 text-contradiction",
  UNRESOLVED: "bg-slate-100 text-slate-600",
};

export function ClaimStatusBadge({ status }: { status: ClaimStatus }) {
  return (
    <span className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${claimStyles[status]}`}>
      {status}
    </span>
  );
}

export { statusLabel };
