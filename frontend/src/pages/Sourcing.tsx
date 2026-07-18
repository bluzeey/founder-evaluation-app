import { Search, Plus } from "lucide-react";

export default function Sourcing() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-ink">Sourcing radar</h1>
        <button className="flex items-center gap-2 rounded-lg bg-action px-4 py-2 text-sm font-medium text-white">
          <Plus size={16} /> Add source
        </button>
      </div>

      <div className="panel">
        <label className="label mb-1.5 block">Natural-language search</label>
        <div className="flex gap-3">
          <div className="flex flex-1 items-center gap-2 rounded-lg border border-slate-300 px-3 py-2">
            <Search size={18} className="text-slate-400" />
            <input
              className="flex-1 bg-transparent text-sm outline-none"
              placeholder="Technical founder in Europe building AI infrastructure, recent product launch…"
            />
          </div>
          <button className="rounded-lg bg-action px-5 py-2 text-sm font-medium text-white">Search</button>
        </div>
      </div>

      <div className="panel py-16 text-center">
        <p className="text-slate-600">Candidate discovery is a future module. Use the dashboard to seed the demo.</p>
      </div>
    </div>
  );
}
