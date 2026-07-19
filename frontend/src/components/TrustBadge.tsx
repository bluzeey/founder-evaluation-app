export function TrustBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  let color = "text-slate-600 bg-slate-100";
  if (pct >= 80) color = "text-verified bg-green-50";
  else if (pct >= 60) color = "text-blue-600 bg-blue-50";
  else if (pct >= 40) color = "text-uncertain bg-amber-50";
  else color = "text-contradiction bg-red-50";
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-semibold tabular ${color}`}>
      Trust {pct}%
    </span>
  );
}

export default TrustBadge;
