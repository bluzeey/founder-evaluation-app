export function DemoBadge({ label = "Synthetic data" }: { label?: string }) {
  return (
    <span className="inline-flex items-center rounded bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-slate-600">
      {label}
    </span>
  );
}

export default DemoBadge;
