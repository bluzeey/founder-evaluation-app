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
        <thead className="bg-manila/40 text-xs font-mono uppercase tracking-wide text-concrete">
          <tr>
            <th className="px-3 py-2">Claim</th>
            <th className="px-3 py-2">Source</th>
            <th className="px-3 py-2">Kind</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2">Trust</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-concrete/10">
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
        className={`cursor-pointer transition ${selected ? "bg-highlight/15" : "hover:bg-manila/30"}`}
      >
        <td className="px-3 py-3">
          <div className="flex items-start gap-2">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setOpen((o) => !o);
              }}
              className="text-concrete hover:text-ink"
            >
              {open ? "−" : "+"}
            </button>
            <div>
              <div className="font-sans font-medium text-ink">{claim.text}</div>
              {claim.contradictionOf && (
                <div className="text-[10px] font-mono text-contradiction">Contradicts {claim.contradictionOf}</div>
              )}
            </div>
          </div>
        </td>
        <td className="px-3 py-3 text-xs text-concrete">
          {deckRef?.slide ? (
            <span className="rounded-sm bg-manila/60 px-1.5 py-0.5 font-mono text-[10px]">Slide {deckRef.slide}</span>
          ) : (
            claim.sourceRefs.map((s) => s.title).join(", ") || "—"
          )}
        </td>
        <td className="px-3 py-3">
          <span className={`rounded-sm border px-1.5 py-0.5 text-[10px] font-mono font-semibold uppercase tracking-wide ${kindColor(claim.claimKind)}`}>
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
          <td colSpan={5} className="bg-manila/30 px-3 py-3 text-xs text-ink/80">
            <div className="space-y-1 font-sans">
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
      return "bg-action/10 text-action border-action/20";
    case "PROJECTION":
      return "bg-inferred/10 text-inferred border-inferred/20";
    case "ASSUMPTION":
      return "bg-uncertain/10 text-uncertain border-uncertain/20";
    case "OPINION":
      return "bg-concrete/10 text-concrete border-concrete/20";
    default:
      return "bg-concrete/10 text-concrete border-concrete/20";
  }
}

export default DeckClaimTable;
