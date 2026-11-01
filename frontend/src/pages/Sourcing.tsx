import { useEffect, useState, useCallback } from "react";
import {
  RotateCw,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  Database,
} from "lucide-react";
import { ManualAIAction, ManualModeIndicator } from "@/components/ManualAI";
import { api } from "@/api/client";
import { useApp } from "@/store/appContext";
import { useAdaptivePolling } from "@/hooks/useAdaptivePolling";
import type {
  BackendPoolItem,
  BackendSourcingSchedule,
  BackendSourcingStatus,
  ApiError,
  SourceConfig,
} from "@/types/backend";

export default function Sourcing() {
  const { activeThesis, state, refreshTheses } = useApp();
  const theses = state.theses;
  const [status, setStatus] = useState<BackendSourcingStatus | null>(null);
  const [schedules, setSchedules] = useState<BackendSourcingSchedule[]>([]);
  const [pool, setPool] = useState<BackendPoolItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionId, setActionId] = useState<string | null>(null);
  const [newSourceByThesis, setNewSourceByThesis] = useState<Record<string, { platform: string; keywords: string }>>({});
  const [seedSummary, setSeedSummary] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [statusData, scheduleData, poolData] = await Promise.all([
        api.sourcing.status(),
        api.sourcing.schedules(),
        api.pool.list(),
      ]);
      setStatus(statusData);
      setSchedules(scheduleData);
      setPool(poolData);
      setError(null);
    } catch (err) {
      const e = err as ApiError;
      setError(e.message || "Failed to load sourcing data");
    } finally {
      setLoading(false);
    }
  }, []);

  const activeCount = status?.active_jobs.length ?? 0;
  const pollInterval = activeCount > 0 ? 5000 : 30000;

  useEffect(() => {
    refresh();
  }, [refresh]);

  useAdaptivePolling(refresh, pollInterval);

  const handleSeed = async () => {
    setActionId("seed");
    try {
      await api.seed();
      await Promise.all([refresh(), refreshTheses()]);
    } catch (err) {
      const e = err as ApiError;
      setError(e.message || "Seed failed");
    } finally {
      setActionId(null);
    }
  };

  const handleSeedAll = async () => {
    setActionId("seed-all");
    setSeedSummary(null);
    try {
      const result = await api.seedAll();
      await Promise.all([refresh(), refreshTheses()]);
      setSeedSummary(
        `Created ${result.theses_created.length} theses, ${result.schedules_created.length} schedules, ${result.founders_created.length} founders, ${result.opportunities_created.length} opportunities, ${result.pool_items_created.length} pool items.`
      );
    } catch (err) {
      const e = err as ApiError;
      setError(e.message || "Seed all failed");
    } finally {
      setActionId(null);
    }
  };

  const handleAddSource = async (thesisId: string, scheduleId: string) => {
    const draft = newSourceByThesis[thesisId];
    if (!draft || !draft.keywords.trim()) return;
    setActionId(`add-source-${thesisId}`);
    try {
      const schedule = schedules.find((s) => s.id === scheduleId);
      if (!schedule) return;
      const updatedSources: SourceConfig[] = [...schedule.sources, { platform: draft.platform, keywords: draft.keywords.trim() }];
      await api.sourcing.updateSchedule(scheduleId, { sources: updatedSources });
      setNewSourceByThesis((prev) => ({ ...prev, [thesisId]: { platform: "linkedin", keywords: "" } }));
      await refresh();
    } catch (err) {
      const e = err as ApiError;
      setError(e.message || "Failed to add source");
    } finally {
      setActionId(null);
    }
  };

  const handleRemoveSource = async (scheduleId: string, index: number) => {
    setActionId(`remove-source-${scheduleId}-${index}`);
    try {
      const schedule = schedules.find((s) => s.id === scheduleId);
      if (!schedule) return;
      const updatedSources = schedule.sources.filter((_, i) => i !== index);
      await api.sourcing.updateSchedule(scheduleId, { sources: updatedSources });
      await refresh();
    } catch (err) {
      const e = err as ApiError;
      setError(e.message || "Failed to remove source");
    } finally {
      setActionId(null);
    }
  };

  const recommendedCount = pool.filter((p) => p.status === "recommended").length;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="label mb-1">Sourcing control room</div>
          <h1 className="text-2xl font-bold text-ink">AI sourcing agent</h1>
          <p className="text-sm text-concrete">
            Run sourcing manually and review existing jobs and recommendations.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleSeed}
            disabled={actionId === "seed"}
            className="flex items-center gap-2 rounded-sm border border-concrete/30 bg-paper px-3 py-2 text-sm font-sans font-medium text-ink hover:bg-manila/40 disabled:opacity-50"
          >
            {actionId === "seed" ? <Loader2 size={16} className="animate-spin" /> : <Database size={16} />}
            Seed
          </button>
          <button
            onClick={handleSeedAll}
            disabled={actionId === "seed-all"}
            className="flex items-center gap-2 rounded-sm border border-verified/30 bg-verified/10 px-3 py-2 text-sm font-sans font-medium text-verified hover:bg-verified/20 disabled:opacity-50"
          >
            {actionId === "seed-all" ? <Loader2 size={16} className="animate-spin" /> : <Database size={16} />}
            Seed all
          </button>
        </div>
      </div>

      <ManualModeIndicator />
      {seedSummary && (
        <div className="rounded-sm border border-verified/30 bg-verified/10 p-3 text-sm text-verified">
          <CheckCircle2 size={16} className="inline" /> {seedSummary}
        </div>
      )}

      {error && (
        <div className="rounded-sm border border-contradiction/30 bg-contradiction/10 p-3 text-sm text-contradiction">
          <div className="flex items-start gap-2">
            <AlertCircle size={16} className="mt-0.5 shrink-0" />
            <div className="flex-1">
              <div className="font-semibold">Could not connect to backend</div>
              <div className="mt-0.5">{error}</div>
              <button
                onClick={refresh}
                disabled={loading}
                className="mt-2 inline-flex items-center gap-1 rounded-sm border border-contradiction/30 bg-paper px-2 py-1 text-xs font-sans font-medium text-contradiction hover:bg-contradiction/10 disabled:opacity-50"
              >
                {loading ? <Loader2 size={12} className="animate-spin" /> : <RotateCw size={12} />}
                Retry
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Status cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-sm border border-concrete/20 bg-paper p-4">
          <div className="label">Active jobs</div>
          <div className="mt-1 font-display text-2xl font-bold text-ink">
            {loading ? "—" : activeCount}
          </div>
        </div>
        <div className="rounded-sm border border-concrete/20 bg-paper p-4">
          <div className="label">Recommended pool</div>
          <div className="mt-1 font-display text-2xl font-bold text-ink">
            {loading ? "—" : recommendedCount}
          </div>
        </div>
        <div className="rounded-sm border border-concrete/20 bg-paper p-4">
          <div className="label">Saved source settings</div>
          <div className="mt-1 font-display text-2xl font-bold text-ink">
            {loading ? "—" : schedules.length}
          </div>
        </div>
        <div className="rounded-sm border border-concrete/20 bg-paper p-4">
          <div className="label">Automatic sourcing</div>
          <div className="mt-1 text-sm font-medium text-ink">
            Off · manual runs only
          </div>
        </div>
      </div>

      {/* Schedules */}
      <div className="panel space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-display text-lg font-semibold text-ink">Manual sourcing settings</h3>
          <ManualAIAction label="Run AI pool sourcing" disabled={theses.length === 0} onComplete={refresh}
            run={() => api.pool.refresh(activeThesis?.id ?? theses[0]?.id)} />
        </div>

        {schedules.length === 0 && !loading && (
          <div className="text-sm text-concrete">
            No source settings saved yet. You can still run sourcing once for a thesis.
          </div>
        )}

        <div className="space-y-3">
          {theses.map((thesis) => {
            const schedule = schedules.find((s) => s.thesis_id === thesis.id);
            return (
              <div
                key={thesis.id}
                className="flex flex-col gap-3 rounded-sm border border-concrete/20 bg-manila/20 p-4"
              >
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <div className="font-sans font-semibold text-ink">{thesis.name}</div>
                    <div className="text-xs text-concrete">
                      {thesis.sectors.join(", ")} · {thesis.stages.join(", ")} · {thesis.geographies.join(", ")}
                    </div>
                    {schedule && (
                      <div className="mt-1 text-xs text-concrete">
                        Saved sources for manual runs
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <ManualAIAction label="Run AI sourcing" onComplete={refresh}
                      run={() => api.sourcing.runNow(thesis.id)} />
                  </div>
                </div>

                {/* Sources */}
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-ink">Sources</div>
                  <div className="flex flex-wrap gap-2">
                    {(schedule?.sources ?? []).map((source, index) => (
                      <span
                        key={index}
                        className="inline-flex items-center gap-1 rounded-sm border border-concrete/20 bg-paper px-2 py-1 text-xs font-mono text-ink"
                      >
                        {source.platform}: {source.keywords}
                        <button
                          onClick={() => handleRemoveSource(schedule!.id, index)}
                          disabled={actionId === `remove-source-${schedule!.id}-${index}`}
                          className="text-concrete hover:text-contradiction disabled:opacity-50"
                        >
                          {actionId === `remove-source-${schedule!.id}-${index}` ? <Loader2 size={12} className="animate-spin" /> : <XCircle size={12} />}
                        </button>
                      </span>
                    ))}
                    {(schedule?.sources ?? []).length === 0 && (
                      <span className="text-xs text-concrete">No sources configured. Add LinkedIn/Twitter keyword searches below.</span>
                    )}
                  </div>
                  <div className="flex flex-wrap items-end gap-2">
                    <select
                      className="rounded-sm border border-concrete/30 bg-paper px-2 py-1.5 text-sm font-sans outline-none"
                      value={newSourceByThesis[thesis.id]?.platform ?? "linkedin"}
                      onChange={(e) =>
                        setNewSourceByThesis((prev) => ({ ...prev, [thesis.id]: { ...(prev[thesis.id] ?? { keywords: "" }), platform: e.target.value } }))
                      }
                    >
                      <option value="linkedin">LinkedIn</option>
                      <option value="twitter">Twitter/X</option>
                      <option value="other">Other</option>
                    </select>
                    <input
                      className="min-w-[200px] flex-1 rounded-sm border border-concrete/30 bg-paper px-2 py-1.5 text-sm font-sans outline-none"
                      placeholder="Keywords, e.g. AI founder pre-seed"
                      value={newSourceByThesis[thesis.id]?.keywords ?? ""}
                      onChange={(e) =>
                        setNewSourceByThesis((prev) => ({ ...prev, [thesis.id]: { ...(prev[thesis.id] ?? { platform: "linkedin" }), keywords: e.target.value } }))
                      }
                    />
                    <button
                      onClick={() => schedule && handleAddSource(thesis.id, schedule.id)}
                      disabled={!schedule || !newSourceByThesis[thesis.id]?.keywords.trim() || actionId === `add-source-${thesis.id}`}
                      className="flex items-center gap-1 rounded-sm border border-verified/30 bg-verified/10 px-3 py-1.5 text-sm font-sans font-medium text-verified hover:bg-verified/20 disabled:opacity-50"
                    >
                      {actionId === `add-source-${thesis.id}` ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                      Add source
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Pool */}
      <div className="panel space-y-4">
        <h3 className="font-display text-lg font-semibold text-ink">Founder pool</h3>
        {pool.length === 0 && !loading && (
          <div className="text-sm text-concrete">No pool items yet. Run sourcing or refresh the pool.</div>
        )}
        <div className="grid grid-cols-1 gap-3">
          {pool.map((item) => (
            <div
              key={item.id}
              className="flex flex-col gap-3 rounded-sm border border-concrete/20 bg-paper p-4 md:flex-row md:items-start md:justify-between"
            >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-sans font-semibold text-ink">{item.name}</span>
                    <PoolStatusBadge status={item.status} />
                    {item.source && (
                      <span className="rounded-sm bg-manila/50 px-1.5 py-0.5 text-[10px] font-mono font-semibold uppercase text-concrete">
                        {item.source}
                      </span>
                    )}
                  </div>
                  <div className="text-sm text-concrete">
                    {item.current_company ?? "—"} · {item.role ?? "—"} · {item.location ?? "—"}
                  </div>
                  <div className="mt-1 text-sm text-ink/80">{item.reason}</div>
                  {item.source_url && (
                    <a
                      href={item.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-1 inline-block text-xs text-action hover:underline"
                    >
                      Source
                    </a>
                  )}
                </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function PoolStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    recommended: "bg-action/10 text-action",
    approved: "bg-verified/10 text-verified",
    dismissed: "bg-concrete/10 text-concrete",
  };
  return (
    <span className={`rounded-sm px-1.5 py-0.5 text-[10px] font-mono font-semibold uppercase ${styles[status] ?? styles.recommended}`}>
      {status}
    </span>
  );
}
