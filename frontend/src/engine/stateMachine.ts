import type { CaseStatus, Duration, EvidenceEvent, InvestmentCase } from "@/domain/types";

export function calculateTimeRemaining(decisionDeadline: string): Duration {
  const deadline = new Date(decisionDeadline).getTime();
  const now = Date.now();
  const remaining = Math.max(0, deadline - now);
  const totalSeconds = Math.floor(remaining / 1000);
  const totalHours = 24;
  const percentRemaining = Math.max(0, Math.min(100, (totalSeconds / (totalHours * 3600)) * 100));

  return {
    totalSeconds,
    days: Math.floor(totalSeconds / 86400),
    hours: Math.floor((totalSeconds % 86400) / 3600),
    minutes: Math.floor((totalSeconds % 3600) / 60),
    seconds: totalSeconds % 60,
    isExpired: now > deadline,
    percentRemaining,
  };
}

export function applyEvent(investmentCase: InvestmentCase, event: EvidenceEvent): InvestmentCase {
  return {
    ...investmentCase,
    history: [...(investmentCase.history || []), event],
    // Snapshots are append-only; the previous case remains unchanged in caller history if stored separately.
  };
}

export function isTerminal(status: CaseStatus): boolean {
  return ["INVESTED", "DECLINED", "MONITORING"].includes(status);
}

export function canDecide(status: CaseStatus): boolean {
  return ["ASSOCIATE_REVIEW", "PARTNER_REVIEW", "SCREENING"].includes(status);
}

export function statusLabel(status: CaseStatus): string {
  return status
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
