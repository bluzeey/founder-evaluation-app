import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Search, Loader2, ArrowRight } from "lucide-react";
import { api } from "@/api/client";
import type { BackendFounder, BackendOpportunity } from "@/types/backend";

export default function Discovery() {
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
      const text = [
        f.name,
        f.current_company,
        f.role,
        f.location,
        f.source_reason,
      ]
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
            Every AI-sourced lead becomes a founder case. Click a card to see the detailed breakdown.
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

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {rows.map((founder) => {
            const opp = opportunities[founder.id];
            const snapshot = founder.latest_score_snapshot;
            const score = snapshot ? Math.round(snapshot.founder_score) : undefined;
            const confidence = snapshot
              ? `${Math.round(snapshot.overall_confidence * 100)}%`
              : "—";
            const link = opp ? `/cases/${opp.opportunity_id}` : "/cases";
            return (
              <Link
                key={founder.id}
                to={link}
                className="index-card group flex flex-col gap-4 border-l-4 border-l-action hover:border-l-action/80"
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-manila font-display text-sm font-bold text-ink">
                    {founder.name
                      .split(" ")
                      .map((n) => n[0])
                      .join("")
                      .slice(0, 2)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="font-sans font-semibold text-ink">{founder.name}</h3>
                    </div>
                    <div className="mt-0.5 text-sm text-concrete truncate">
                      {founder.current_company || "—"} · {founder.role || "—"} ·{" "}
                      {founder.location || "—"}
                    </div>
                    {founder.source_url && (
                      <a
                        href={founder.source_url}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="mt-1 block truncate text-xs text-action hover:underline"
                      >
                        {founder.source_url}
                      </a>
                    )}
                  </div>
                </div>

                <div className="space-y-1">
                  <div className="label">Idea / why they surfaced</div>
                  <p className="text-sm font-medium text-ink line-clamp-3">
                    {founder.source_reason || "No reason provided."}
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-sm border border-concrete/20 bg-manila/30 p-3">
                    <div className="label">Founder score</div>
                    <div className="mt-1 font-display text-xl font-bold tabular text-ink">
                      {score ?? "—"}
                    </div>
                  </div>
                  <div className="rounded-sm border border-concrete/20 bg-manila/30 p-3">
                    <div className="label">Confidence</div>
                    <div className="mt-1 font-display text-xl font-bold tabular text-ink">
                      {confidence}
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between border-t border-concrete/10 pt-3">
                  <span className="text-xs text-concrete group-hover:text-action">
                    View detailed breakdown
                  </span>
                  <ArrowRight
                    size={16}
                    className="text-concrete transition-colors group-hover:text-action"
                  />
                </div>
              </Link>
            );
          })}
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
