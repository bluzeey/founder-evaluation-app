export function TrustBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  let color = "text-concrete bg-concrete/10 border-concrete/20";
  if (pct >= 80) color = "text-verified bg-verified/10 border-verified/20";
  else if (pct >= 60) color = "text-action bg-action/10 border-action/20";
  else if (pct >= 40) color = "text-uncertain bg-uncertain/10 border-uncertain/20";
  else color = "text-contradiction bg-contradiction/10 border-contradiction/20";
  return (
    <span className={`rounded-sm border px-2 py-0.5 text-[10px] font-mono font-semibold uppercase tracking-wide tabular ${color}`}>
      Trust {pct}%
    </span>
  );
}

export default TrustBadge;
