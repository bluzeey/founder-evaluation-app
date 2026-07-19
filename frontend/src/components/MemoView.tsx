import type { CaseMemo } from "@/domain/types";

export function MemoView({ memo }: { memo: CaseMemo }) {
  return (
    <div className="panel space-y-5">
      <Section title="Company snapshot" bullets={[memo.companySnapshot]} />
      <Section title="Investment hypotheses" bullets={memo.hypotheses} />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Section title="Strengths" bullets={memo.swot.strengths} color="text-verified" />
        <Section title="Weaknesses" bullets={memo.swot.weaknesses} color="text-contradiction" />
        <Section title="Opportunities" bullets={memo.swot.opportunities} color="text-action" />
        <Section title="Threats" bullets={memo.swot.threats} color="text-uncertain" />
      </div>
      <Section title="Problem and product" bullets={[memo.problemAndProduct]} />
      <Section title="Traction and KPIs" bullets={memo.tractionKpis} />
      {memo.contradictions.length > 0 && (
        <Section title="Contradictions and unresolved risks" bullets={memo.contradictions} color="text-contradiction" />
      )}
      <Section title="Missing information" bullets={memo.missingInformation} color="text-slate-600" />
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
        <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Recommended next action</div>
        <div className="mt-1 text-sm font-medium text-ink">{memo.recommendedNextAction}</div>
      </div>
      <div>
        <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Citations</div>
        <ul className="mt-1 space-y-1 text-xs text-slate-600">
          {Object.entries(memo.claimCitations).map(([label, ids]) => (
            <li key={label}>
              <span className="font-medium">{label}:</span> {ids.join(", ")}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function Section({
  title,
  bullets,
  color,
}: {
  title: string;
  bullets: string[];
  color?: string;
}) {
  if (bullets.length === 0 || (bullets.length === 1 && !bullets[0])) return null;
  return (
    <div>
      <div className="label mb-1.5">{title}</div>
      <ul className="space-y-1 text-sm text-slate-700">
        {bullets.map((b, i) => (
          <li key={i} className={color || "text-slate-700"}>
            • {b}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default MemoView;
