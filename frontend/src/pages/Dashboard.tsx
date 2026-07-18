import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, AlertCircle, Sparkles, Loader2, UserPlus, X, ExternalLink } from "lucide-react";
import { api } from "@/lib/api";
import type { Founder, FounderPoolItem } from "@/types";

export default function Dashboard() {
  const [founders, setFounders] = useState<Founder[]>([]);
  const [pool, setPool] = useState<FounderPoolItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [poolLoading, setPoolLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [seeded, setSeeded] = useState(false);

  useEffect(() => {
    load();
    loadPool();
  }, []);

  async function load() {
    setLoading(true);
    try {
      const data = await api.listFounders();
      setFounders(data);
    } finally {
      setLoading(false);
    }
  }

  async function loadPool() {
    setPoolLoading(true);
    try {
      const data = await api.listFounderPool("recommended");
      setPool(data);
    } finally {
      setPoolLoading(false);
    }
  }

  async function seedDemo() {
    await api.seed();
    setSeeded(true);
    await load();
  }

  async function refreshPool() {
    setRefreshing(true);
    try {
      await api.refreshFounderPool();
      // Poll briefly for the eager/demo result.
      setTimeout(loadPool, 1500);
    } finally {
      setRefreshing(false);
    }
  }

  async function approveItem(item: FounderPoolItem) {
    await api.approvePoolItem(item.id);
    await Promise.all([loadPool(), load()]);
  }

  async function dismissItem(item: FounderPoolItem) {
    await api.dismissPoolItem(item.id);
    await loadPool();
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-ink">Investor dashboard</h1>
        <div className="flex gap-3">
          <button
            onClick={seedDemo}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Seed hackathon demo
          </button>
          <Link
            to="/applications/new"
            className="flex items-center gap-2 rounded-lg bg-action px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            <Plus size={16} /> Add founder
          </Link>
        </div>
      </div>

      {seeded && (
        <div className="flex items-center gap-2 rounded-lg bg-blue-50 p-3 text-sm text-action">
          <AlertCircle size={16} /> Demo seeded. A low-data founder profile is ready for assessment.
        </div>
      )}

      <div className="panel">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-ink">AI-sourced founder pool</h2>
            <p className="text-xs text-slate-500">
              The sourcing agent discovers interesting founders matching your thesis.
            </p>
          </div>
          <button
            onClick={refreshPool}
            disabled={refreshing}
            className="flex items-center gap-2 rounded-lg bg-action px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {refreshing ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
            {refreshing ? "Finding…" : "Find more founders"}
          </button>
        </div>

        {poolLoading ? (
          <div className="py-8 text-center text-sm text-slate-500">Loading recommendations…</div>
        ) : pool.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-300 py-8 text-center text-sm text-slate-500">
            No recommendations yet. Click “Find more founders” to run the AI sourcing agent.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {pool.map((item) => (
              <div
                key={item.id}
                className="flex flex-col rounded-lg border border-slate-200 bg-slate-50 p-4"
              >
                <div className="mb-2 flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-ink">{item.name}</h3>
                    <p className="text-xs text-slate-600">
                      {item.role} · {item.current_company || "—"}
                    </p>
                    {item.location && <p className="text-xs text-slate-500">{item.location}</p>}
                  </div>
                  <div className="flex gap-1">
                    <button
                      onClick={() => approveItem(item)}
                      className="rounded-md p-1.5 text-green-600 hover:bg-green-100"
                      title="Add to pipeline"
                    >
                      <UserPlus size={16} />
                    </button>
                    <button
                      onClick={() => dismissItem(item)}
                      className="rounded-md p-1.5 text-slate-500 hover:bg-slate-200"
                      title="Dismiss"
                    >
                      <X size={16} />
                    </button>
                  </div>
                </div>
                <p className="mb-3 flex-1 text-sm text-slate-700">{item.reason}</p>
                <div className="flex flex-wrap gap-2">
                  {item.source_url && (
                    <a
                      href={item.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-1 text-xs text-blue-600 hover:underline"
                    >
                      <ExternalLink size={12} /> Source
                    </a>
                  )}
                  {item.linkedin_url && (
                    <a
                      href={item.linkedin_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-blue-600 hover:underline"
                    >
                      LinkedIn
                    </a>
                  )}
                  {item.github_url && (
                    <a
                      href={item.github_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-slate-700 hover:underline"
                    >
                      GitHub
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {loading ? (
        <div className="panel py-12 text-center text-slate-500">Loading opportunities…</div>
      ) : founders.length === 0 ? (
        <div className="panel py-16 text-center">
          <p className="text-slate-600">No founders yet. Seed the demo or add a founder.</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Founder</th>
                <th className="px-4 py-3">Company</th>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Confidence</th>
                <th className="px-4 py-3">Coverage</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {founders.map((f) => {
                const snap = f.latest_score_snapshot;
                const isColdStart = !snap || snap.overall_confidence < 0.3;
                return (
                  <tr key={f.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-medium text-ink">{f.name}</td>
                    <td className="px-4 py-3 text-slate-600">{f.current_company || "—"}</td>
                    <td className="px-4 py-3 tabular font-semibold">{snap?.founder_score ?? "—"}</td>
                    <td className="px-4 py-3 tabular">{snap ? `${Math.round(snap.overall_confidence * 100)}%` : "—"}</td>
                    <td className="px-4 py-3 tabular">{snap ? `${Math.round(snap.evidence_coverage * 100)}%` : "—"}</td>
                    <td className="px-4 py-3">
                      {isColdStart ? (
                        <span className="rounded-full bg-amber-50 px-2 py-1 text-xs font-semibold text-uncertain">
                          Assessment recommended
                        </span>
                      ) : (
                        <span className="rounded-full bg-green-50 px-2 py-1 text-xs font-semibold text-verified">
                          Ready for review
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-3">
                        <Link to={`/founders/${f.id}`} className="text-action hover:underline">
                          Profile
                        </Link>
                        <Link to={`/assessment/${f.id}`} className="text-action hover:underline">
                          Assess
                        </Link>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
