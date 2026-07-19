import { useState } from "react";
import type { Claim } from "@/domain/types";
import { ClaimStatusBadge } from "./StatusBadge";
import { TrustBadge } from "./TrustBadge";

export function DeckClaimTable({
  claims,
  selectedId,
  onSelect,
}: {
  claims: Claim[];
  selectedId?: string;
  onSelect?: (id: string) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase text-slate-500">
          <tr>
            <th className="px-3 py-2">Claim</th>
            <th className="px-3 py-2">Source</th>
            <th className="px-3 py-2">Kind</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2">Trust</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {claims.map((c) => (
            <ClaimRow
              key={c.id}
              claim={c}
              selected={selectedId === c.id}
              onClick={() => onSelect?.(c.id)}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ClaimRow({ claim, selected, onClick }: { claim: Claim; selected: boolean; onClick: () => void }) {
  const [open, setOpen] = useState(false);
  const deckRef = claim.sourceRefs.find((s) => s.sourceType === "DECK");
  return (
    <>
      <tr
        onClick={onClick}
        className={`cursor-pointer transition ${selected ? "bg-blue-50" : "hover:bg-slate-50"}`}
      >
        <td className="px-3 py-3">
          <div className="flex items-start gap-2">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setOpen((o) => !o);
              }}
              className="text-slate-400 hover:text-ink"
            >
              {open ? "−" : "+"}
            </button>
            <div>
              <div className="font-medium text-ink">{claim.text}</div>
              {claim.contradictionOf && (
                <div className="text-[10px] text-contradiction">Contradicts {claim.contradictionOf}</div>
              )}
            </div>
          </div>
        </td>
        <td className="px-3 py-3 text-xs text-slate-600">
          {deckRef?.slide ? (
            <span className="rounded bg-slate-100 px-1.5 py-0.5">Slide {deckRef.slide}</span>
          ) : (
            claim.sourceRefs.map((s) => s.title).join(", ") || "—"
          )}
        </td>
        <td className="px-3 py-3">
          <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${kindColor(claim.claimKind)}`}>
            {claim.claimKind || "UNKNOWN"}
          </span>
        </td>
        <td className="px-3 py-3">
          <ClaimStatusBadge status={claim.status} />
        </td>
        <td className="px-3 py-3">
          <TrustBadge score={claim.trustScore} />
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={5} className="bg-slate-50 px-3 py-3 text-xs text-slate-700">
            <div className="space-y-1">
              <div>
                <span className="font-semibold">Category:</span> {claim.category}
              </div>
              <div>
                <span className="font-semibold">Sources:</span>{" "}
                {claim.sourceRefs.map((s) => `${s.title}${s.slide ? ` (slide ${s.slide})` : ""}`).join("; ")}
              </div>
              <div>
                <span className="font-semibold">Trust components:</span> reliability{" "}
                {Math.round(claim.sourceReliability * 100)}%, extraction {Math.round(claim.extractionConfidence * 100)}%,
                corroboration {Math.round(claim.corroboration * 100)}%, recency {Math.round(claim.recency * 100)}%,
                specificity {Math.round(claim.evidenceSpecificity * 100)}%
                {claim.contradictionPenalty > 0 && (
                  <span className="text-contradiction">
                    {" "}
                    − penalty {Math.round(claim.contradictionPenalty * 100)}%
                  </span>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function kindColor(kind?: Claim["claimKind"]) {
  switch (kind) {
    case "FACT":
      return "bg-blue-50 text-action";
    case "PROJECTION":
      return "bg-purple-50 text-inferred";
    case "ASSUMPTION":
      return "bg-amber-50 text-uncertain";
    case "OPINION":
      return "bg-slate-100 text-slate-600";
    default:
      return "bg-slate-100 text-slate-600";
  }
}

export default DeckClaimTable;
