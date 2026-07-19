import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { Search, Filter, UserPlus, Eye, Mail, Activity } from "lucide-react";
import { DEMO_CASES, TALENT_SIGNALS, getDemoPerson, getDemoCompany } from "@/data/demoCases";
import { useApp } from "@/store/appContext";
import { CaseStatusBadge } from "@/components/StatusBadge";
import { DemoBadge } from "@/components/DemoBadge";
import type { CaseStatus, TalentSignal } from "@/domain/types";

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
  const [tag, setTag] = useState("All");
  const [status, setStatus] = useState("All");
  const [dimension, setDimension] = useState("All");
  const [minConfidence, setMinConfidence] = useState(0);

  const rows = useMemo(() => {
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
    }));

    const combined = [
      ...talentRows.map((t) => ({ ...t, isInbound: false })),
      ...(caseRows as unknown as Array<TalentSignal & { isInbound: boolean }>),
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
  }, [query, source, tag, status, dimension, minConfidence]);

  const activateTalent = (caseId: string) => {
    setCaseOverride(caseId, { status: "SCREENING", nextAction: "Activated from Discovery. Schedule shared screening call within 24h." });
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">Discovery Inbox</h1>
          <p className="text-sm text-slate-500">Outbound talent signals and inbound applications converge into shared screening.</p>
        </div>
        <div className="flex items-center gap-2">
          <DemoBadge />
        </div>
      </div>

      <div className="panel space-y-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-ink">
          <Filter size={16} /> Filters
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-6">
          <div className="flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2">
            <Search size={16} className="text-slate-400" />
            <input
              className="flex-1 bg-transparent text-sm outline-none"
              placeholder="Search person or project"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <FilterSelect value={source} onChange={setSource} options={["All", ...SOURCE_OPTIONS]} label="Source" />
          <FilterSelect value={tag} onChange={setTag} options={["All", ...TAG_OPTIONS]} label="Thesis tag" />
          <FilterSelect value={status} onChange={setStatus} options={["All", ...STATUS_OPTIONS]} label="Status" />
          <FilterSelect value={dimension} onChange={setDimension} options={["All", ...DIM_OPTIONS]} label="Signal dimension" />
          <div>
            <label className="text-[10px] font-semibold uppercase text-slate-500">Min confidence</label>
            <input
              type="range"
              min={0}
              max={100}
              value={Math.round(minConfidence * 100)}
              onChange={(e) => setMinConfidence(Number(e.target.value) / 100)}
              className="w-full"
            />
            <div className="text-xs text-slate-600">{Math.round(minConfidence * 100)}%</div>
          </div>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Person</th>
              <th className="px-4 py-3">Current project / artifact</th>
              <th className="px-4 py-3">Source</th>
              <th className="px-4 py-3">Thesis tags</th>
              <th className="px-4 py-3">Strongest signal</th>
              <th className="px-4 py-3">Confidence</th>
              <th className="px-4 py-3">Trend</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Why today</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((row) => (
              <tr key={row.id} className="hover:bg-slate-50">
                <td className="px-4 py-3">
                  <div className="font-medium text-ink">{row.person}</div>
                  {row.isInbound && <DemoBadge label="Inbound" />}
                  {!row.isInbound && <DemoBadge label="Talent signal" />}
                </td>
                <td className="px-4 py-3 text-slate-600">{row.currentProject || "—"}</td>
                <td className="px-4 py-3 text-slate-600">{row.sourceChannel}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {row.thesisTags.slice(0, 3).map((t) => (
                      <span key={t} className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">
                        {t}
                      </span>
            ))}
          </div>
        </td>
        <td className="px-4 py-3 text-sm font-medium text-ink">{row.strongestSignal}</td>
        <td className="px-4 py-3 tabular">{Math.round(row.signalConfidence * 100)}%</td>
        <td className="px-4 py-3 text-xs text-slate-600">{row.momentumTrend.replace(/_/g, " ")}</td>
        <td className="px-4 py-3">
          <CaseStatusBadge status={row.status} />
        </td>
        <td className="px-4 py-3 text-xs text-slate-600 max-w-xs">{row.whyAppeared}</td>
        <td className="px-4 py-3">
          <div className="flex flex-wrap gap-2">
            {(() => {
              const cid = row.caseId || row.id;
              return (
                <>
                  <Link to={`/cases/${cid}`} className="rounded-md p-1.5 text-slate-600 hover:bg-slate-100" title="Open profile">
                    <Eye size={16} />
                  </Link>
                  <button
                    className="rounded-md p-1.5 text-slate-600 hover:bg-slate-100"
                    title="Monitor"
                    onClick={() => setCaseOverride(cid, { status: "MONITORING", nextAction: "Monitoring: wait for next signal." })}
                  >
                    <Activity size={16} />
                  </button>
                  <button
                    className="rounded-md p-1.5 text-slate-600 hover:bg-slate-100"
                    title="Research"
                    onClick={() => alert("Demo: research request would queue external lookups.")}
                  >
                    <Search size={16} />
                  </button>
                  <button
                    className="rounded-md p-1.5 text-green-600 hover:bg-green-100"
                    title="Activate"
                    onClick={() => activateTalent(cid)}
                  >
                    <UserPlus size={16} />
                  </button>
                  <button
                    className="rounded-md p-1.5 text-blue-600 hover:bg-blue-100"
                    title="Invite to apply"
                    onClick={() => setCaseOverride(cid, { status: "AWAITING_APPLICATION", nextAction: "Invitation sent; awaiting application form." })}
                  >
                    <Mail size={16} />
                  </button>
                </>
              );
            })()}
          </div>
        </td>
      </tr>
    ))}
  </tbody>
</table>

        {rows.length === 0 && (
          <div className="py-8 text-center text-sm text-slate-500">No signals match the current filters.</div>
        )}
      </div>

      <div className="panel text-sm text-slate-600">
        <strong>Demo script:</strong> Start with the cold-start talent, activate it, then open the inbound application to view deck claims.
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
    <div>
      <label className="text-[10px] font-semibold uppercase text-slate-500">{label}</label>
      <select
        className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1 text-sm outline-none"
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
