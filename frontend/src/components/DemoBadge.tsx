export function DemoBadge({ label = "Synthetic data" }: { label?: string }) {
  return (
    <span className="inline-flex items-center rounded-sm border border-concrete/30 bg-manila/50 px-2 py-0.5 text-[10px] font-mono font-semibold uppercase tracking-wide text-concrete">
      {label}
    </span>
  );
}

export default DemoBadge;
