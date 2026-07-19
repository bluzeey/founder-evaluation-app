import { useMemo, useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import { Search, MoreHorizontal, UserPlus, Eye, Mail, Activity, ChevronDown, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { DEMO_CASES, TALENT_SIGNALS, getDemoPerson, getDemoCompany } from "@/data/demoCases";
import { useApp } from "@/store/appContext";
import { CaseStatusBadge } from "@/components/StatusBadge";
import { DemoBadge } from "@/components/DemoBadge";
import { api } from "@/api/client";
import type { CaseStatus, TalentSignal } from "@/domain/types";
import type { BackendPoolItem, ApiError } from "@/types/backend";

const STATUS_OPTIONS: CaseStatus[] = [
  "DISCOVERED",
  "ACTIVATION_READY",
  "AWAITING_APPLICATION",
  "SCREENING",
  "DILIGENCE",
  "VALIDATION_HOLD",
  "ASSOCIATE_REVIEW",
  "PARTNER_REVIEW",
];

const SOURCE_OPTIONS = ["Hackathon result + GitHub", "Inbound application", "Inbound deck + company"];
const TAG_OPTIONS = ["AI Infrastructure", "AI Software", "Developer Tools", "Pre-seed", "United States", "Germany"];
const DIM_OPTIONS = ["Founder", "Traction", "Vision/Product", "Market", "Differentiation"];

export default function Discovery() {
  const { setCaseOverride } = useApp();
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("All");
  const [status, setStatus] = useState("All");
  const [dimension, setDimension] = useState("All");
  const [tag, setTag] = useState("All");
  const [minConfidence, setMinConfidence] = useState(0);
  const [showMoreFilters, setShowMoreFilters] = useState(false);
  const [openActionId, setOpenActionId] = useState<string | null>(null);
  const [livePool, setLivePool] = useState<BackendPoolItem[]>([]);
  const [liveLoading, setLiveLoading] = useState(false);
  const [liveActionId, setLiveActionId] = useState<string | null>(null);
  const actionRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (actionRef.current && !actionRef.current.contains(e.target as Node)) {
        setOpenActionId(null);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLiveLoading(true);
    api.pool
      .list()
      .then((items) => {
        if (!cancelled) setLivePool(items);
      })
      .catch(() => {
        // Live backend is optional; keep demo data visible.
      })
      .finally(() => {
        if (!cancelled) setLiveLoading(false);
      });
    const interval = setInterval(() => {
      api.pool.list().then(setLivePool).catch(() => {});
    }, 10000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const rows = useMemo(() => {
    const liveRows: Array<TalentSignal & { isInbound: boolean; live: boolean }> = livePool.map((item) => ({
      id: item.id,
      person: item.name,
      currentProject: item.current_company,
      artifactUrl: item.source_url,
      sourceChannel: "AI sourcing",
      thesisTags: [],
      strongestSignal: item.reason,
      signalConfidence: 0.5,
      signalDate: item.created_at,
      momentumTrend: "INSUFFICIENT_HISTORY",
      status: "DISCOVERED" as CaseStatus,
      whyAppeared: item.reason,
      caseId: undefined,
      isInbound: false,
      live: true,
    }));
    const talentRows: TalentSignal[] = TALENT_SIGNALS;
    const caseRows = DEMO_CASES.map((c) => ({
      id: c.id,
      person: c.founderIds.map((id) => getDemoPerson(id)?.name || id).join(", "),
      currentProject: c.companyId ? getDemoCompany(c.companyId)?.name : c.claims.find((x) => x.category === "PRODUCT")?.text,
      sourceChannel: c.sourceChannel,
      thesisTags: c.companyId
        ? [getDemoCompany(c.companyId)?.sector, getDemoCompany(c.companyId)?.geography, "pre-seed"].filter(Boolean) as string[]
        : ["AI Infrastructure", "Developer Tools", "Germany"],
      strongestSignal: c.triggeredRules[0] || c.drivers.sort((a, b) => b.score - a.score)[0]?.key || "—",
      signalConfidence: Math.max(...c.drivers.map((d) => d.confidence)),
      signalDate: c.createdAt,
      momentumTrend: c.axes.find((a) => a.key === "FOUNDER")?.trend || "INSUFFICIENT_HISTORY",
      status: c.status,
      whyAppeared: c.inboundOrOutbound === "OUTBOUND" ? "Outbound talent signal" : "Inbound application",
      caseId: c.id,
      isInbound: c.inboundOrOutbound === "INBOUND",
      live: false,
    }));

    const combined = [
      ...liveRows,
      ...talentRows.map((t) => ({ ...t, isInbound: false, live: false })),
      ...(caseRows as unknown as Array<TalentSignal & { isInbound: boolean; live: boolean }>),
    ].filter((row) => {
      const q = query.toLowerCase();
      const matchesQuery =
        !q ||
        row.person.toLowerCase().includes(q) ||
        row.currentProject?.toLowerCase().includes(q) ||
        row.sourceChannel.toLowerCase().includes(q);
      const matchesSource = source === "All" || row.sourceChannel.includes(source);
      const matchesTag = tag === "All" || row.thesisTags.some((t) => t.toLowerCase().includes(tag.toLowerCase()));
      const matchesStatus = status === "All" || row.status === status;
      const matchesDim = dimension === "All" || row.strongestSignal.toLowerCase().includes(dimension.toLowerCase());
      const matchesConfidence = row.signalConfidence >= minConfidence;
      return matchesQuery && matchesSource && matchesTag && matchesStatus && matchesDim && matchesConfidence;
    });
    return combined;
  }, [query, source, tag, status, dimension, minConfidence, livePool]);

  const activeFilters = [
    source !== "All" && { label: source, onRemove: () => setSource("All") },
    status !== "All" && { label: status, onRemove: () => setStatus("All") },
    dimension !== "All" && { label: dimension, onRemove: () => setDimension("All") },
    tag !== "All" && { label: tag, onRemove: () => setTag("All") },
    minConfidence > 0 && { label: `≥${Math.round(minConfidence * 100)}% conf`, onRemove: () => setMinConfidence(0) },
  ].filter(Boolean) as { label: string; onRemove: () => void }[];

  const activateTalent = (caseId: string) => {
    setCaseOverride(caseId, { status: "SCREENING", nextAction: "Activated from Discovery. Schedule shared screening call within 24h." });
  };

  const handleLiveApprove = async (id: string) => {
    setLiveActionId(id);
    try {
      await api.pool.approve(id);
      const updated = await api.pool.list();
      setLivePool(updated);
    } catch (err) {
      const e = err as ApiError;
      alert(e.message || "Approve failed");
    } finally {
      setLiveActionId(null);
    }
  };

  const handleLiveDismiss = async (id: string) => {
    setLiveActionId(id);
    try {
      await api.pool.dismiss(id);
      const updated = await api.pool.list();
      setLivePool(updated);
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
        <div className="flex items-center gap-2">
          <DemoBadge />
        </div>
      </div>

      {/* Filters */}
      <div className="rounded-sm border border-concrete/20 bg-manila/20 p-3 shadow-paper">
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex min-w-[180px] flex-1 items-center gap-2 rounded-sm border border-concrete/30 bg-paper px-2 py-1.5">
            <Search size={14} className="text-concrete" />
            <input
              className="min-w-0 flex-1 bg-transparent text-sm font-sans outline-none"
              placeholder="Search person or project"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <FilterSelect value={source} onChange={setSource} options={["All", ...SOURCE_OPTIONS]} label="Source" />
          <FilterSelect value={status} onChange={setStatus} options={["All", ...STATUS_OPTIONS]} label="Status" />
          <FilterSelect value={dimension} onChange={setDimension} options={["All", ...DIM_OPTIONS]} label="Signal" />
          <button
            onClick={() => setShowMoreFilters((s) => !s)}
            className="flex items-center gap-1 rounded-sm border border-concrete/30 bg-paper px-2 py-1.5 text-sm font-sans font-medium text-ink hover:bg-manila/40"
          >
            More <ChevronDown size={14} className={`transition-transform ${showMoreFilters ? "rotate-180" : ""}`} />
          </button>
        </div>

        {showMoreFilters && (
          <div className="mt-2 grid grid-cols-1 gap-2 border-t border-concrete/20 pt-2 sm:grid-cols-2 lg:grid-cols-4">
            <FilterSelect value={tag} onChange={setTag} options={["All", ...TAG_OPTIONS]} label="Thesis tag" />
            <div>
              <label className="label mb-0.5 block">Min confidence</label>
              <input
                type="range"
                min={0}
                max={100}
                value={Math.round(minConfidence * 100)}
                onChange={(e) => setMinConfidence(Number(e.target.value) / 100)}
                className="w-full"
              />
              <div className="font-mono text-[10px] text-concrete">{Math.round(minConfidence * 100)}%</div>
            </div>
          </div>
        )}

        {activeFilters.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 border-t border-concrete/20 pt-3">
            <span className="text-xs text-concrete">Active:</span>
            {activeFilters.map((f, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1 rounded-sm border border-concrete/20 bg-paper px-2 py-1 text-xs font-mono text-ink"
              >
                {f.label}
                <button onClick={f.onRemove} className="text-concrete hover:text-contradiction">
                  ×
                </button>
              </span>
            ))}
            <button
              onClick={() => {
                setSource("All");
                setStatus("All");
                setDimension("All");
                setTag("All");
                setMinConfidence(0);
              }}
              className="text-xs text-action hover:underline"
            >
              Clear all
            </button>
          </div>
        )}
      </div>

      {/* Results */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-concrete">
            <span className="font-display font-semibold text-ink">{rows.length}</span> signals
            {liveLoading && <Loader2 size={14} className="animate-spin text-concrete" />}
          </div>
        </div>

        {rows.map((row) => {
          const cid = row.caseId || row.id;
          const isOpen = openActionId === cid;
          return (
            <div
              key={row.id}
              className="index-card relative grid grid-cols-1 gap-4 lg:grid-cols-12"
            >
              {/* Left: identity */}
              <div className="lg:col-span-4">
                <div className="flex items-start gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-manila font-display text-sm font-bold text-ink">
                    {row.person.split(" ").map((n) => n[0]).join("").slice(0, 2)}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-sans font-semibold text-ink">{row.person}</h3>
                      <CaseStatusBadge status={row.status} />
                      {row.live && (
                        <span className="rounded-sm bg-action/10 px-1.5 py-0.5 text-[10px] font-mono font-semibold uppercase text-action">
                          Live
                        </span>
                      )}
                    </div>
                    <div className="mt-0.5 text-sm text-concrete truncate">
                      {row.currentProject || "—"} · {row.sourceChannel}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {row.thesisTags.slice(0, 3).map((t) => (
                        <span key={t} className="rounded-sm border border-concrete/20 bg-manila/50 px-1.5 py-0.5 text-[10px] font-mono text-concrete">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Middle: signal */}
              <div className="lg:col-span-4">
                <div className="label mb-1">Strongest signal</div>
                <div className="text-sm font-medium text-ink">{row.strongestSignal}</div>
                <div className="mt-2 flex items-center gap-3">
                  <div className="h-2 w-24 overflow-hidden rounded-full bg-concrete/15">
                    <div
                      className={`h-full ${row.signalConfidence >= 0.7 ? "bg-verified" : row.signalConfidence >= 0.5 ? "bg-action" : "bg-uncertain"}`}
                      style={{ width: `${Math.round(row.signalConfidence * 100)}%` }}
                    />
                  </div>
                  <span className="font-mono text-xs font-semibold tabular text-concrete">
                    {Math.round(row.signalConfidence * 100)}% conf
                  </span>
                </div>
                <div className="mt-1 text-xs text-concrete">{row.momentumTrend.replace(/_/g, " ")}</div>
              </div>

              {/* Right: why + actions */}
              <div className="flex flex-col justify-between lg:col-span-4">
                <div className="text-sm text-concrete line-clamp-2">
                  <span className="text-ink/70">Why today:</span> {row.whyAppeared}
                </div>
                <div className="mt-3 flex items-center gap-2">
                  {row.live ? (
                    <>
                      <button
                        onClick={() => handleLiveApprove(row.id)}
                        disabled={liveActionId === row.id}
                        className="flex items-center gap-1 rounded-sm border border-verified/30 bg-verified/10 px-3 py-1.5 text-sm font-sans font-medium text-verified hover:bg-verified/20 disabled:opacity-50"
                      >
                        {liveActionId === row.id ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                        Approve
                      </button>
                      <button
                        onClick={() => handleLiveDismiss(row.id)}
                        disabled={liveActionId === row.id}
                        className="flex items-center gap-1 rounded-sm border border-concrete/30 bg-paper px-3 py-1.5 text-sm font-sans font-medium text-concrete hover:bg-manila/40 disabled:opacity-50"
                      >
                        {liveActionId === row.id ? <Loader2 size={14} className="animate-spin" /> : <XCircle size={14} />}
                        Dismiss
                      </button>
                    </>
                  ) : (
                    <>
                      <Link
                        to={`/cases/${cid}`}
                        className="flex items-center gap-1 rounded-sm bg-action px-3 py-1.5 text-sm font-sans font-medium text-paper hover:bg-action-dark"
                      >
                        <Eye size={14} /> Open
                      </Link>
                      <button
                        onClick={() => activateTalent(cid)}
                        className="flex items-center gap-1 rounded-sm border border-verified/30 bg-verified/10 px-3 py-1.5 text-sm font-sans font-medium text-verified hover:bg-verified/20"
                      >
                        <UserPlus size={14} /> Activate
                      </button>
                      <div className="relative" ref={isOpen ? actionRef : undefined}>
                        <button
                          onClick={() => setOpenActionId(isOpen ? null : cid)}
                          className="rounded-sm border border-concrete/30 bg-paper p-1.5 text-concrete hover:bg-manila/40"
                        >
                          <MoreHorizontal size={18} />
                        </button>
                        {isOpen && (
                          <div className="absolute right-0 top-full z-10 mt-1 w-44 rounded-sm border border-concrete/20 bg-paper shadow-paper-lg">
                            <button
                              onClick={() => {
                                setCaseOverride(cid, { status: "MONITORING", nextAction: "Monitoring: wait for next signal." });
                                setOpenActionId(null);
                              }}
                              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-ink hover:bg-manila/40"
                            >
                              <Activity size={14} /> Monitor
                            </button>
                            <button
                              onClick={() => {
                                alert("Demo: research request would queue external lookups.");
                                setOpenActionId(null);
                              }}
                              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-ink hover:bg-manila/40"
                            >
                              <Search size={14} /> Research
                            </button>
                            <button
                              onClick={() => {
                                setCaseOverride(cid, { status: "AWAITING_APPLICATION", nextAction: "Invitation sent; awaiting application form." });
                                setOpenActionId(null);
                              }}
                              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-ink hover:bg-manila/40"
                            >
                              <Mail size={14} /> Invite to apply
                            </button>
                          </div>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {rows.length === 0 && (
          <div className="panel py-12 text-center text-sm text-concrete">No signals match the current filters.</div>
        )}
      </div>

      <div className="panel border-manila-dark/30 bg-manila/20 text-sm text-concrete">
        <strong className="text-ink">Demo script:</strong> Start with the cold-start talent, activate it, then open the inbound application to view deck claims.
      </div>
    </div>
  );
}

function FilterSelect({
  value,
  onChange,
  options,
  label,
}: {
  value: string;
  onChange: (v: string) => void;
  options: string[];
  label: string;
}) {
  return (
    <div className="w-[132px]">
      <label className="label mb-0.5 block text-[10px]">{label}</label>
      <select
        className="w-full rounded-sm border border-concrete/30 bg-paper px-2 py-1.5 text-sm font-sans outline-none"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </div>
  );
}
