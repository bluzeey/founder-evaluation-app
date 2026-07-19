import { useMemo, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { api } from "@/api/client";
import type { BackendPoolItem, ApiError } from "@/types/backend";

export default function Discovery() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [livePool, setLivePool] = useState<BackendPoolItem[]>([]);
  const [liveLoading, setLiveLoading] = useState(false);
  const [liveActionId, setLiveActionId] = useState<string | null>(null);

  const load = () => {
    setLiveLoading(true);
    api.pool
      .list("recommended")
      .then((items) => setLivePool(items))
      .catch(() => {})
      .finally(() => setLiveLoading(false));
  };

  useEffect(() => {
    load();
    const interval = setInterval(() => {
      api.pool.list("recommended").then(setLivePool).catch(() => {});
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const rows = useMemo(() => {
    const q = query.toLowerCase();
    return livePool.filter((item) => {
      if (!q) return true;
      return (
        item.name.toLowerCase().includes(q) ||
        (item.current_company || "").toLowerCase().includes(q) ||
        (item.source || "").toLowerCase().includes(q) ||
        (item.reason || "").toLowerCase().includes(q)
      );
    });
  }, [query, livePool]);

  const handleApprove = async (id: string) => {
    setLiveActionId(id);
    try {
      const result = await api.pool.approve(id);
      setLivePool((prev) => prev.filter((i) => i.id !== id));
      navigate(`/cases/${result.opportunity_id}`);
    } catch (err) {
      const e = err as ApiError;
      alert(e.message || "Approve failed");
    } finally {
      setLiveActionId(null);
    }
  };

  const handleDismiss = async (id: string) => {
    setLiveActionId(id);
    try {
      await api.pool.dismiss(id);
      setLivePool((prev) => prev.filter((i) => i.id !== id));
    } catch (err) {
      const e = err as ApiError;
      alert(e.message || "Dismiss failed");
    } finally {
      setLiveActionId(null);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="label mb-1">Discovery Inbox</div>
          <h1 className="text-2xl font-bold text-ink">Signals waiting on a desk</h1>
          <p className="text-sm text-concrete">Outbound talent signals and inbound applications converge into shared screening.</p>
        </div>
      </div>

      {/* Search */}
      <div className="rounded-sm border border-concrete/20 bg-manila/20 p-3 shadow-paper">
        <div className="flex min-w-[180px] max-w-md items-center gap-2 rounded-sm border border-concrete/30 bg-paper px-2 py-1.5">
          <Search size={14} className="text-concrete" />
          <input
            className="min-w-0 flex-1 bg-transparent text-sm font-sans outline-none"
            placeholder="Search person, company, source, or reason"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Results */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-concrete">
            <span className="font-display font-semibold text-ink">{rows.length}</span> signals
            {liveLoading && <Loader2 size={14} className="animate-spin text-concrete" />}
          </div>
        </div>

        {rows.map((item) => (
          <div key={item.id} className="index-card relative grid grid-cols-1 gap-4 lg:grid-cols-12">
            {/* Left: identity */}
            <div className="lg:col-span-4">
              <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-manila font-display text-sm font-bold text-ink">
                  {item.name
                    .split(" ")
                    .map((n) => n[0])
                    .join("")
                    .slice(0, 2)}
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-sans font-semibold text-ink">{item.name}</h3>
                    {item.source && (
                      <span className="rounded-sm bg-manila/50 px-1.5 py-0.5 text-[10px] font-mono font-semibold uppercase text-concrete">
                        {item.source}
                      </span>
                    )}
                  </div>
                  <div className="mt-0.5 text-sm text-concrete truncate">
                    {item.current_company || "—"} · {item.source || "AI sourcing"}
                  </div>
                  {item.source_url && (
                    <a
                      href={item.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-1 block truncate text-xs text-action hover:underline"
                    >
                      {item.source_url}
                    </a>
                  )}
                </div>
              </div>
            </div>

            {/* Middle: signal */}
            <div className="lg:col-span-5">
              <div className="label mb-1">Why they surfaced</div>
              <div className="text-sm font-medium text-ink">{item.reason || "No reason provided."}</div>
              <div className="mt-1 text-xs text-concrete">
                Discovered {new Date(item.created_at).toLocaleDateString()}
              </div>
            </div>

            {/* Right: actions */}
            <div className="flex flex-col justify-center lg:col-span-3">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleApprove(item.id)}
                  disabled={liveActionId === item.id}
                  className="flex items-center gap-1 rounded-sm border border-verified/30 bg-verified/10 px-3 py-1.5 text-sm font-sans font-medium text-verified hover:bg-verified/20 disabled:opacity-50"
                >
                  {liveActionId === item.id ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                  Approve
                </button>
                <button
                  onClick={() => handleDismiss(item.id)}
                  disabled={liveActionId === item.id}
                  className="flex items-center gap-1 rounded-sm border border-concrete/30 bg-paper px-3 py-1.5 text-sm font-sans font-medium text-concrete hover:bg-manila/40 disabled:opacity-50"
                >
                  {liveActionId === item.id ? <Loader2 size={14} className="animate-spin" /> : <XCircle size={14} />}
                  Dismiss
                </button>
              </div>
            </div>
          </div>
        ))}

        {rows.length === 0 && (
          <div className="panel py-12 text-center text-sm text-concrete">
            {liveLoading ? "Loading signals…" : "No recommended signals waiting."}
          </div>
        )}
      </div>

      <div className="panel border-manila-dark/30 bg-manila/20 text-sm text-concrete">
        <strong className="text-ink">Workflow:</strong> Approve a sourced signal to create a founder case and start evaluation.
      </div>
    </div>
  );
}
