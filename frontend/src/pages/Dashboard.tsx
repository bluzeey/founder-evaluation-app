import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";
import type { Founder } from "@/types";

export default function Dashboard() {
  const [founders, setFounders] = useState<Founder[]>([]);
  const [loading, setLoading] = useState(true);
  const [seeded, setSeeded] = useState(false);

  useEffect(() => {
    load();
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

  async function seedDemo() {
    await api.seed();
    setSeeded(true);
    await load();
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
