import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileText, CheckCircle2, Loader2, AlertCircle } from "lucide-react";
import { extractDeck } from "@/agents/deckExtractor";
import { claimsFromDeck } from "@/agents/claimExtractor";
import { DemoBadge } from "@/components/DemoBadge";
import { DeckClaimTable } from "@/components/DeckClaimTable";
import type { DeckExtractionResult } from "@/domain/types";

const DEMO_DECKS = [
  { value: "case-contradictory-traction", label: "Demo deck: TractionAI (contradictory traction)" },
  { value: "case-founder-spike", label: "Demo deck: PromptBridge (strong founder, weak idea)" },
  { value: "case-cold-start", label: "Demo deck: ML Code Review (cold-start talent)" },
];

const SECTIONS = [
  {
    id: "founder",
    title: "Founder and team",
    fields: ["Founder name", "Founder email", "LinkedIn", "GitHub", "Team size"],
  },
  {
    id: "idea",
    title: "Idea and market",
    fields: ["Problem", "Target customer", "Market geography", "Competition"],
  },
  {
    id: "product",
    title: "Product and user evidence",
    fields: ["Product URL", "Demo video", "User feedback", "Usage metrics"],
  },
  {
    id: "business",
    title: "Business, distribution, economics, traction, and scale",
    fields: ["Revenue", "Go-to-market", "Check size", "Valuation cap", "Distribution plan"],
  },
];

export default function Apply() {
  const navigate = useNavigate();
  const [company, setCompany] = useState("");
  const [founder, setFounder] = useState("");
  const [deckName, setDeckName] = useState(DEMO_DECKS[0].value);
  const [productUrl, setProductUrl] = useState("");
  const [consent, setConsent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [extraction, setExtraction] = useState<DeckExtractionResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleExtract = async () => {
    if (!deckName) return;
    setLoading(true);
    setError(null);
    try {
      const result = await extractDeck(deckName, "Demo deck content");
      setExtraction(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Extraction failed");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!company || !founder || !consent) {
      setError("Company, founder, and consent are required.");
      return;
    }
    setLoading(true);
    await new Promise((r) => setTimeout(r, 400));
    setLoading(false);
    navigate(`/cases/${deckName}`);
  };

  const deckClaims = extraction ? claimsFromDeck("new-application", extraction) : [];

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">Inbound application</h1>
          <p className="text-sm text-slate-500">Upload a deck and answer follow-up questions. Every answer becomes a claim.</p>
        </div>
        <DemoBadge />
      </div>

      <form onSubmit={handleSubmit} className="panel space-y-5">
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
          <div>
            <label className="label mb-1.5 block">Company name</label>
            <input
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              placeholder="Acme AI"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
            />
          </div>
          <div>
            <label className="label mb-1.5 block">Founder name</label>
            <input
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              placeholder="Jane Doe"
              value={founder}
              onChange={(e) => setFounder(e.target.value)}
            />
          </div>
          <div>
            <label className="label mb-1.5 block">Deck (demo fixtures)</label>
            <select
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={deckName}
              onChange={(e) => setDeckName(e.target.value)}
            >
              {DEMO_DECKS.map((d) => (
                <option key={d.value} value={d.value}>
                  {d.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label mb-1.5 block">Product URL</label>
            <input
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              placeholder="https://"
              value={productUrl}
              onChange={(e) => setProductUrl(e.target.value)}
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <input
            id="consent"
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
          />
          <label htmlFor="consent" className="text-sm text-slate-700">
            I consent to having this deck parsed into structured claims for investor review.
          </label>
        </div>

        <div className="flex gap-3">
          <button
            type="button"
            onClick={handleExtract}
            disabled={loading || !deckName}
            className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <FileText size={16} />}
            {loading ? "Extracting…" : "Extract deck claims"}
          </button>
          <button
            type="submit"
            disabled={loading || !company || !founder || !consent}
            className="flex items-center gap-2 rounded-lg bg-action px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
            Submit application
          </button>
        </div>

        {extraction && (
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
            <div className="flex items-center gap-2 font-semibold text-ink">
              <FileText size={16} /> Extraction result
            </div>
            <div className="mt-2 grid grid-cols-3 gap-3 text-xs">
              <div className="rounded bg-white p-2 border border-slate-200">
                <div className="text-slate-500">Slides</div>
                <div className="font-semibold text-ink">{extraction.slides.length}</div>
              </div>
              <div className="rounded bg-white p-2 border border-slate-200">
                <div className="text-slate-500">Claims</div>
                <div className="font-semibold text-ink">{deckClaims.length}</div>
              </div>
              <div className="rounded bg-white p-2 border border-slate-200">
                <div className="text-slate-500">Missing sections</div>
                <div className="font-semibold text-ink">{extraction.missingSections.length}</div>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            <AlertCircle size={16} className="inline" /> {error}
          </div>
        )}
      </form>

      {extraction && (
        <div className="panel space-y-4">
          <h3 className="text-lg font-semibold text-ink">Deck claims</h3>
          <DeckClaimTable claims={deckClaims} />
          <div className="text-xs text-slate-500">
            Projections and assumptions are shown as distinct from verified facts. Click a claim to see its slide citation.
          </div>
        </div>
      )}

      <div className="panel space-y-4">
        <h3 className="text-lg font-semibold text-ink">Application follow-up</h3>
        <p className="text-sm text-slate-500">
          Questions already answered by the deck are marked. Only missing decision-critical follow-ups are shown by default.
        </p>
        <div className="space-y-3">
          {SECTIONS.map((section) => (
            <div key={section.id} className="rounded-lg border border-slate-200">
              <button className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-semibold text-ink hover:bg-slate-50">
                {section.title}
                <span className="text-xs font-normal text-slate-500">
                  {section.fields.filter((f) => !answeredByDeck(f)).length} critical follow-ups
                </span>
              </button>
              <div className="border-t border-slate-100 px-4 py-3">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  {section.fields.map((field) => (
                    <div key={field} className="flex items-center gap-2">
                      <input
                        className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
                        placeholder={field}
                      />
                      {answeredByDeck(field) && (
                        <span className="rounded bg-green-50 px-1.5 py-0.5 text-[10px] font-semibold text-verified">
                          Deck
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function answeredByDeck(field: string) {
  const deckAnswered = ["Founder name", "Problem", "Product URL", "Revenue", "Go-to-market", "Check size"];
  return deckAnswered.some((f) => field.toLowerCase().includes(f.toLowerCase()));
}
