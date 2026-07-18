import { useState } from "react";
import { Search, Plus, Loader2, ExternalLink, User, Building2, MapPin, Link2 } from "lucide-react";
import { api } from "@/lib/api";
import type { Founder } from "@/types";

const DEFAULT_CHANNELS = ["linkedin", "twitter", "github", "news", "company_blog"];

export default function Sourcing() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Founder | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const founder = await api.researchFounder({
        query: query.trim(),
        channels: DEFAULT_CHANNELS,
        auto_score: true,
      });
      setResult(founder);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Research failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-ink">Sourcing radar</h1>
      </div>

      <form onSubmit={handleSearch} className="panel">
        <label className="label mb-1.5 block">Natural-language founder search</label>
        <div className="flex gap-3">
          <div className="flex flex-1 items-center gap-2 rounded-lg border border-slate-300 px-3 py-2">
            <Search size={18} className="text-slate-400" />
            <input
              className="flex-1 bg-transparent text-sm outline-none"
              placeholder="Maya Shah, ContextLoop, Bangalore…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="flex items-center gap-2 rounded-lg bg-action px-5 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
            {loading ? "Researching…" : "Research founder"}
          </button>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Searches LinkedIn, X/Twitter, GitHub, news, and company blogs via Umans AI web search.
        </p>
      </form>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {result && (
        <div className="panel space-y-4">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-lg font-bold text-ink">{result.name}</h2>
              <div className="mt-1 flex flex-wrap items-center gap-3 text-sm text-slate-600">
                {result.current_company && (
                  <span className="flex items-center gap-1">
                    <Building2 size={14} /> {result.current_company}
                  </span>
                )}
                {result.role && (
                  <span className="flex items-center gap-1">
                    <User size={14} /> {result.role}
                  </span>
                )}
                {result.location && (
                  <span className="flex items-center gap-1">
                    <MapPin size={14} /> {result.location}
                  </span>
                )}
              </div>
            </div>
            <div className="flex gap-2">
              {result.linkedin_url && (
                <a
                  href={result.linkedin_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
                >
                  LinkedIn <ExternalLink size={12} />
                </a>
              )}
              {result.github_url && (
                <a
                  href={result.github_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
                >
                  GitHub <ExternalLink size={12} />
                </a>
              )}
            </div>
          </div>

          {result.ai_research_summary && (
            <div className="rounded-lg bg-slate-50 p-4 text-sm text-slate-700">
              {result.ai_research_summary}
            </div>
          )}

          {result.latest_score_snapshot && (
            <div className="grid grid-cols-3 gap-4">
              <div className="rounded-lg border border-slate-200 p-3 text-center">
                <p className="text-xs text-slate-500">Founder score</p>
                <p className="text-xl font-bold text-ink">
                  {result.latest_score_snapshot.founder_score.toFixed(0)}
                </p>
              </div>
              <div className="rounded-lg border border-slate-200 p-3 text-center">
                <p className="text-xs text-slate-500">Confidence</p>
                <p className="text-xl font-bold text-ink">
                  {(result.latest_score_snapshot.overall_confidence * 100).toFixed(0)}%
                </p>
              </div>
              <div className="rounded-lg border border-slate-200 p-3 text-center">
                <p className="text-xs text-slate-500">Coverage</p>
                <p className="text-xl font-bold text-ink">
                  {(result.latest_score_snapshot.evidence_coverage * 100).toFixed(0)}%
                </p>
              </div>
            </div>
          )}

          {result.ai_research_sources && result.ai_research_sources.length > 0 && (
            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Sources
              </h3>
              <ul className="space-y-1">
                {result.ai_research_sources.map((url, idx) => (
                  <li key={idx} className="flex items-center gap-1 text-xs text-slate-600">
                    <Link2 size={12} />
                    <a href={url} target="_blank" rel="noreferrer" className="truncate hover:underline">
                      {url}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
