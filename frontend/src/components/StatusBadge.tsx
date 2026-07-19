import type { CaseStatus, ClaimStatus } from "@/domain/types";
import { statusLabel } from "@/engine/stateMachine";

const statusStyles: Record<CaseStatus, string> = {
  DISCOVERED: "bg-concrete/10 text-concrete border-concrete/20",
  ACTIVATION_READY: "bg-verified/10 text-verified border-verified/30",
  AWAITING_APPLICATION: "bg-uncertain/10 text-uncertain border-uncertain/30",
  SCREENING: "bg-action/10 text-action border-action/30",
  DILIGENCE: "bg-uncertain/10 text-uncertain border-uncertain/30",
  VALIDATION_HOLD: "bg-contradiction/10 text-contradiction border-contradiction/30",
  ASSOCIATE_REVIEW: "bg-inferred/10 text-inferred border-inferred/30",
  PARTNER_REVIEW: "bg-ink/10 text-ink border-ink/20",
  INVESTED: "bg-verified/15 text-verified border-verified/40",
  DECLINED: "bg-concrete/15 text-concrete border-concrete/30",
  MONITORING: "bg-uncertain/10 text-uncertain border-uncertain/30",
};

export function CaseStatusBadge({ status }: { status: CaseStatus }) {
  return (
    <span className={`rounded-sm border px-2 py-0.5 text-[10px] font-mono font-semibold uppercase tracking-wide ${statusStyles[status]}`}>
      {statusLabel(status)}
    </span>
  );
}

const claimStyles: Record<ClaimStatus, string> = {
  DECLARED: "bg-concrete/10 text-concrete border-concrete/20",
  INFERRED: "bg-inferred/10 text-inferred border-inferred/30",
  VERIFIED: "bg-verified/10 text-verified border-verified/30",
  CONTRADICTED: "bg-contradiction/10 text-contradiction border-contradiction/30",
  UNRESOLVED: "bg-concrete/10 text-concrete border-concrete/20",
};

export function ClaimStatusBadge({ status }: { status: ClaimStatus }) {
  return (
    <span className={`rounded-sm border px-1.5 py-0.5 text-[10px] font-mono font-semibold uppercase tracking-wide ${claimStyles[status]}`}>
      {status}
    </span>
  );
}

export { statusLabel };
