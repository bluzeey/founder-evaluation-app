import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Clock, MessageSquare, Paperclip, Mic } from "lucide-react";
import { api } from "@/lib/api";
import type { AssessmentModule, AssessmentPlan, ScoreSnapshot } from "@/types";

const moduleDetails: Record<AssessmentModule, { title: string; scenario: string; prompt: string }> = {
  sales_objection: {
    title: "Sales and objection handling",
    scenario: "The AI acts as a skeptical prospective customer.",
    prompt:
      '"We already use Notion, Google Drive, and ChatGPT. Your product sounds useful, but not important enough for us to change our workflow." Respond as the founder selling to this customer.',
  },
  prioritization: {
    title: "Prioritization under constraints",
    scenario: "You have two engineers, eight weeks of runway, ₹5 lakh in capital, and five possible initiatives.",
    prompt:
      "Select one initiative, explain why, define what you will not build, and specify the evidence you expect to collect.",
  },
  belief_updating: {
    title: "Belief updating",
    scenario: "New evidence contradicts your original go-to-market strategy.",
    prompt:
      "You selected enterprise sales. New evidence shows a nine-month procurement cycle and strong self-serve adoption. Decide whether to revise your strategy and explain what evidence caused the change.",
  },
  scaling_leadership: {
    title: "Scaling and leadership",
    scenario: "Your company has grown from 5 to 40 employees and decisions still require your approval.",
    prompt: "Describe your first 14 days of action to remove the bottleneck, clarify ownership, and retain senior talent.",
  },
  setback_ownership: {
    title: "Setback and ownership",
    scenario: "Your largest pilot customer rejects the product. You have four months of runway.",
    prompt: "Walk through your next seven days, including how you engage your co-founder and team.",
  },
  problem_framing: {
    title: "Problem framing",
    scenario: "Explain the customer problem without describing your product.",
    prompt:
      "Who experiences the problem most intensely? Who pays? What currently happens instead? What evidence would convince you the problem is not important enough to pursue?",
  },
  claim_calibration: {
    title: "Claim calibration and verification",
    scenario: "Review claims extracted from your deck.",
    prompt: "For each claim, mark it as verified fact, estimate, assumption, founder-reported, outdated, incorrect, or unable to disclose. Attach evidence where possible.",
  },
  role_work_sample: {
    title: "Role-specific work sample",
    scenario: "Complete a short task relevant to your role.",
    prompt: "Submit a brief work sample or plan as instructed.",
  },
};

export default function AssessmentSession() {
  const { founderId } = useParams<{ founderId: string }>();
  const navigate = useNavigate();
  const [plan, setPlan] = useState<AssessmentPlan | null>(null);
  const [responses, setResponses] = useState<Record<AssessmentModule, string>>({} as Record<AssessmentModule, string>);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<ScoreSnapshot | null>(null);

  useEffect(() => {
    if (!founderId) return;
    api.planAssessment(founderId).then((p) => {
      setPlan(p);
      const init: Record<AssessmentModule, string> = {} as Record<AssessmentModule, string>;
      p.recommended_modules.forEach((m) => (init[m] = ""));
      setResponses(init);
    });
  }, [founderId]);

  if (!plan) return <div className="panel py-12 text-center">Planning assessment…</div>;

  const currentModule = plan.recommended_modules[currentIndex];
  const detail = moduleDetails[currentModule];
  const allAnswered = plan.recommended_modules.every((m) => responses[m]?.trim().length > 10);

  async function submit() {
    if (!founderId || !plan) return;
    setSubmitting(true);
    const snapshot = await api.simulateAssessment(founderId, plan.recommended_modules, responses);
    setResult(snapshot);
    setSubmitting(false);
  }

  if (result) {
    return (
      <div className="mx-auto max-w-2xl space-y-6">
        <div className="panel text-center">
          <h2 className="mb-2 text-xl font-bold text-ink">Assessment complete</h2>
          <p className="mb-4 text-slate-600">The score has been updated with generated evidence.</p>
          <div className="mb-6 grid grid-cols-3 gap-4">
            <div className="rounded-lg bg-slate-50 p-4">
              <div className="label">Founder Score</div>
              <div className="text-3xl font-bold tabular text-ink">{result.founder_score}</div>
            </div>
            <div className="rounded-lg bg-slate-50 p-4">
              <div className="label">Confidence</div>
              <div className="text-3xl font-bold tabular text-ink">{Math.round(result.overall_confidence * 100)}%</div>
            </div>
            <div className="rounded-lg bg-slate-50 p-4">
              <div className="label">Coverage</div>
              <div className="text-3xl font-bold tabular text-ink">{Math.round(result.evidence_coverage * 100)}%</div>
            </div>
          </div>
          <button
            onClick={() => navigate(`/founders/${founderId}`)}
            className="rounded-lg bg-action px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
          >
            View updated profile
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
      <div className="panel lg:col-span-1">
        <div className="label mb-3">Modules</div>
        <div className="space-y-2">
          {plan.recommended_modules.map((m, i) => (
            <button
              key={m}
              onClick={() => setCurrentIndex(i)}
              className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm ${
                i === currentIndex ? "bg-ink text-white" : "bg-slate-50 text-slate-700 hover:bg-slate-100"
              }`}
            >
              <span>{moduleDetails[m].title}</span>
              {responses[m]?.trim().length > 10 && <span className="text-xs opacity-70">done</span>}
            </button>
          ))}
        </div>
        <div className="mt-6 flex items-center gap-2 text-xs text-slate-500">
          <Clock size={14} /> ~30 minutes total
        </div>
      </div>

      <div className="space-y-4 lg:col-span-3">
        <div className="panel">
          <div className="mb-1 text-xs font-semibold uppercase text-slate-500">
            Module {currentIndex + 1} of {plan.recommended_modules.length}
          </div>
          <h2 className="mb-2 text-xl font-bold text-ink">{detail.title}</h2>
          <p className="mb-4 text-sm text-slate-600">{detail.scenario}</p>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-action">
              <MessageSquare size={14} /> AI
            </div>
            <p className="text-sm text-ink">{detail.prompt}</p>
          </div>
        </div>

        <div className="panel">
          <label className="label mb-1.5 block">Your response</label>
          <textarea
            value={responses[currentModule] || ""}
            onChange={(e) => setResponses({ ...responses, [currentModule]: e.target.value })}
            rows={8}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-action focus:outline-none"
            placeholder="Type your response…"
          />
          <div className="mt-3 flex items-center gap-3">
            <button className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50">
              <Paperclip size={14} /> Attach
            </button>
            <button className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50">
              <Mic size={14} /> Record
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <button
            disabled={currentIndex === 0}
            onClick={() => setCurrentIndex((i) => i - 1)}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
          >
            Previous
          </button>
          {currentIndex < plan.recommended_modules.length - 1 ? (
            <button
              onClick={() => setCurrentIndex((i) => i + 1)}
              className="rounded-lg bg-action px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Next module
            </button>
          ) : (
            <button
              disabled={!allAnswered || submitting}
              onClick={submit}
              className="rounded-lg bg-action px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40"
            >
              {submitting ? "Grading…" : "Submit assessment"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
