import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Loader2, ArrowUpRight } from "lucide-react";
import { api } from "@/api/client";
import type { BackendFounder, BackendOpportunity } from "@/types/backend";

export default function Discovery() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [founders, setFounders] = useState<BackendFounder[]>([]);
  const [opportunities, setOpportunities] = useState<Record<string, BackendOpportunity>>({});
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [founderData, oppData] = await Promise.all([
        api.founders.list(),
        api.opportunities.list(),
      ]);
      setFounders(founderData);
      const map: Record<string, BackendOpportunity> = {};
      oppData.forEach((opp) => {
        map[opp.founder_id] = opp;
      });
      setOpportunities(map);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const interval = setInterval(() => {
      Promise.all([api.founders.list(), api.opportunities.list()])
        .then(([founderData, oppData]) => {
          setFounders(founderData);
          const map: Record<string, BackendOpportunity> = {};
          oppData.forEach((opp) => {
            map[opp.founder_id] = opp;
          });
          setOpportunities(map);
        })
        .catch(() => {});
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const rows = useMemo(() => {
    const q = query.toLowerCase();
    return founders.filter((f) => {
      if (!q) return true;
      const text = [f.name, f.current_company, f.role, f.location, f.source_reason]
        .join(" ")
        .toLowerCase();
      return text.includes(q);
    });
  }, [query, founders]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="label mb-1">Discovery</div>
          <h1 className="text-2xl font-bold text-ink">All sourced founders</h1>
          <p className="text-sm text-concrete">
            Every AI-sourced lead becomes a founder case. Click a row to see the detailed breakdown.
          </p>
        </div>
      </div>

      {/* Search */}
      <div className="rounded-sm border border-concrete/20 bg-manila/20 p-3 shadow-paper">
        <div className="flex min-w-[180px] max-w-md items-center gap-2 rounded-sm border border-concrete/30 bg-paper px-2 py-1.5">
          <Search size={14} className="text-concrete" />
          <input
            className="min-w-0 flex-1 bg-transparent text-sm font-sans outline-none"
            placeholder="Search founder, company, role, or idea"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Results */}
      <div className="space-y-3">
        <div className="flex items-center justify-between text-sm text-concrete">
          <div className="flex items-center gap-2">
            <span className="font-display font-semibold text-ink">{rows.length}</span> founders
            {loading && <Loader2 size={14} className="animate-spin text-concrete" />}
          </div>
        </div>

        <div className="overflow-x-auto rounded-sm border border-concrete/20 bg-paper shadow-paper">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-concrete/20 bg-manila/30">
              <tr>
                <th className="px-4 py-3 font-sans font-semibold text-ink">Founder</th>
                <th className="px-4 py-3 font-sans font-semibold text-ink">Idea / why they surfaced</th>
                <th className="px-4 py-3 font-sans font-semibold text-ink">Score</th>
                <th className="px-4 py-3 font-sans font-semibold text-ink">Confidence</th>
                <th className="px-4 py-3 font-sans font-semibold text-ink"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-concrete/10">
              {rows.map((founder) => {
                const opp = opportunities[founder.id];
                const snapshot = founder.latest_score_snapshot;
                const score = snapshot ? Math.round(snapshot.founder_score) : "—";
                const confidence = snapshot
                  ? `${Math.round(snapshot.overall_confidence * 100)}%`
                  : "—";
                const link = opp ? `/cases/${opp.opportunity_id}` : "/cases";
                return (
                  <tr
                    key={founder.id}
                    onClick={() => navigate(link)}
                    className="cursor-pointer transition-colors hover:bg-manila/20"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-manila font-display text-sm font-bold text-ink">
                          {founder.name
                            .split(" ")
                            .map((n) => n[0])
                            .join("")
                            .slice(0, 2)}
                        </div>
                        <div className="min-w-0">
                          <div className="font-sans font-semibold text-ink">{founder.name}</div>
                          <div className="text-xs text-concrete truncate">
                            {founder.current_company || "—"} · {founder.role || "—"} ·{" "}
                            {founder.location || "—"}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <p className="max-w-md truncate text-ink/80">
                        {founder.source_reason || "No reason provided."}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-display text-lg font-bold tabular text-ink">{score}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-display text-lg font-bold tabular text-ink">
                        {confidence}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <ArrowUpRight
                        size={16}
                        className="text-concrete transition-colors hover:text-action"
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {rows.length === 0 && (
          <div className="panel py-12 text-center text-sm text-concrete">
            {loading ? "Loading founders…" : "No sourced founders yet. Run sourcing to discover leads."}
          </div>
        )}
      </div>
    </div>
  );
}
