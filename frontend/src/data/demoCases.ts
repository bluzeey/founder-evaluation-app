import type {
  InvestmentCase,
  Claim,
  SourceRef,
  DriverAssessment,
  AxisAssessment,
  CaseMemo,
  DeckExtractionResult,
  TalentSignal,
} from "@/domain/types";

const now = new Date();
const iso = (offsetHours: number) =>
  new Date(now.getTime() + offsetHours * 3600 * 1000).toISOString();

export const DEMO_PEOPLE: Record<
  string,
  { name: string; role: string; location: string; bio: string; demoLabel?: boolean }
> = {
  "talent-a": {
    name: "Alex Rivera",
    role: "Solo builder / ML engineer",
    location: "Berlin, Germany",
    bio: "Former applied scientist at a research lab. Shipped multiple public ML experiments.",
    demoLabel: true,
  },
  "founder-b": {
    name: "Sam Okonkwo",
    role: "Founder / CEO",
    location: "San Francisco, United States",
    bio: "Previously senior engineer at a scaling AI infrastructure company; led two product launches.",
    demoLabel: true,
  },
  "founder-c": {
    name: "Priya Nair",
    role: "Founder / CEO",
    location: "Austin, United States",
    bio: "Technical founder with distributed systems background; ex-platform engineer.",
    demoLabel: true,
  },
};

export const DEMO_COMPANIES: Record<
  string,
  { name: string; sector: string; stage: string; geography: string; demoLabel?: boolean }
> = {
  "weak-idea-co": {
    name: "PromptBridge",
    sector: "AI Software",
    stage: "pre-seed",
    geography: "United States",
    demoLabel: true,
  },
  "traction-ai": {
    name: "TractionAI",
    sector: "AI Infrastructure",
    stage: "pre-seed",
    geography: "United States",
    demoLabel: true,
  },
};

const source = (
  id: string,
  sourceType: SourceRef["sourceType"],
  title: string,
  opts: Partial<SourceRef> = {}
): SourceRef => ({
  id,
  sourceType,
  title,
  observedAt: iso(-72),
  ...opts,
});

const claim = (
  id: string,
  caseId: string,
  category: Claim["category"],
  text: string,
  status: Claim["status"],
  sourceRefs: SourceRef[],
  opts: Partial<Claim> & { slide?: number } = {}
): Claim => {
  const { slide, ...claimOpts } = opts;
  const base = {
    sourceReliability: 0.7,
    extractionConfidence: 0.75,
    corroboration: 0.5,
    recency: 0.8,
    evidenceSpecificity: 0.6,
    contradictionPenalty: 0,
    ...claimOpts,
  };
  const refs = sourceRefs.map((s, i) => (i === 0 && slide !== undefined ? { ...s, slide } : s));
  const trustScore = Math.max(
    0,
    Math.min(
      1,
      0.3 * base.sourceReliability +
        0.2 * base.extractionConfidence +
        0.2 * base.corroboration +
        0.15 * base.recency +
        0.15 * base.evidenceSpecificity -
        0.35 * base.contradictionPenalty
    )
  );
  return {
    id,
    caseId,
    category,
    text,
    status,
    sourceRefs: refs,
    sourceReliability: base.sourceReliability,
    extractionConfidence: base.extractionConfidence,
    corroboration: base.corroboration,
    recency: base.recency,
    evidenceSpecificity: base.evidenceSpecificity,
    contradictionPenalty: base.contradictionPenalty,
    trustScore: Math.round(trustScore * 100) / 100,
    ...claimOpts,
  };
};

const driver = (
  key: DriverAssessment["key"],
  score: number,
  confidence: number,
  trend: DriverAssessment["trend"],
  rubricReason: string,
  supporting: string[],
  opposing: string[],
  missing: string[]
): DriverAssessment => ({
  key,
  score,
  confidence,
  trend,
  supportingClaimIds: supporting,
  opposingClaimIds: opposing,
  missingEvidence: missing,
  rubricReason,
});

const axis = (
  key: AxisAssessment["key"],
  score: number,
  confidence: number,
  trend: AxisAssessment["trend"],
  driverKeys: AxisAssessment["driverKeys"]
): AxisAssessment => ({ key, score, confidence, trend, driverKeys });

const memo = (
  snapshot: string,
  hypotheses: string[],
  swot: CaseMemo["swot"],
  problemAndProduct: string,
  tractionKpis: string[],
  contradictions: string[],
  missing: string[],
  nextAction: string,
  citations: Record<string, string[]>
): CaseMemo => ({
  companySnapshot: snapshot,
  hypotheses,
  swot,
  problemAndProduct,
  tractionKpis,
  contradictions,
  missingInformation: missing,
  recommendedNextAction: nextAction,
  claimCitations: citations,
});

// ===================== CASE A: Outbound cold-start talent =====================

const srcA_event = source("src-a-event", "EVENT", "LLM Hack Berlin result page", {
  url: "https://hack-berlin.example/results",
  excerpt: "Team shipped a working RAG pipeline for code review in 48 hours; won Most Technical Execution.",
});
const srcA_github = source("src-a-github", "GITHUB", "github.com/arivera/ml-code-review", {
  url: "https://github.com/arivera/ml-code-review",
  excerpt: "Repo shows 14 commits over 48 hours, tests, and a README with architecture decisions.",
});
const srcA_web = source("src-a-web", "WEB", "X/Twitter thread on hackathon demo", {
  url: "https://twitter.example/arivera-demo",
  excerpt: "Public demo video with 40+ comments asking about the tooling.",
});
const srcA_form = source("src-a-form", "FORM", "Founder outreach form", {
  excerpt: "Self-reported: no prior funding, no co-founder yet, building nights and weekends.",
});
const srcA_ref = source("src-a-ref", "REFERENCE", "Reference from prior collaborator", {
  excerpt: "Strong executor, fast learner, works well with feedback; commercial experience unknown.",
});

const claimsA: Claim[] = [
  claim(
    "a-1",
    "case-cold-start",
    "TEAM",
    "Shipped a working RAG code-review prototype in 48 hours at LLM Hack Berlin.",
    "VERIFIED",
    [srcA_event, srcA_github],
    { sourceReliability: 0.85, extractionConfidence: 0.85, corroboration: 0.9, recency: 0.95, evidenceSpecificity: 0.9, claimKind: "FACT" }
  ),
  claim(
    "a-2",
    "case-cold-start",
    "TEAM",
    "GitHub repository shows meaningful commit cadence, tests, and architecture notes.",
    "VERIFIED",
    [srcA_github],
    { sourceReliability: 0.85, extractionConfidence: 0.8, corroboration: 0.7, recency: 0.95, evidenceSpecificity: 0.85, claimKind: "FACT" }
  ),
  claim(
    "a-3",
    "case-cold-start",
    "TEAM",
    "Reference describes the builder as a strong executor with fast iteration loops.",
    "VERIFIED",
    [srcA_ref],
    { sourceReliability: 0.75, extractionConfidence: 0.75, corroboration: 0.55, recency: 0.8, evidenceSpecificity: 0.6, claimKind: "OPINION" }
  ),
  claim(
    "a-4",
    "case-cold-start",
    "TRACTION",
    "Public demo thread generated inbound interest from 6+ engineering teams.",
    "INFERRED",
    [srcA_web],
    { sourceReliability: 0.6, extractionConfidence: 0.65, corroboration: 0.4, recency: 0.95, evidenceSpecificity: 0.5, claimKind: "PROJECTION" }
  ),
  claim(
    "a-5",
    "case-cold-start",
    "PRODUCT",
    "Hackathon demo targets code-review latency for AI-assisted developer tooling.",
    "INFERRED",
    [srcA_event, srcA_github],
    { sourceReliability: 0.75, extractionConfidence: 0.75, corroboration: 0.6, recency: 0.95, evidenceSpecificity: 0.65, claimKind: "ASSUMPTION" }
  ),
  claim(
    "a-6",
    "case-cold-start",
    "MARKET",
    "Builder is based in Berlin, Germany and focused on AI developer tools.",
    "VERIFIED",
    [srcA_form, srcA_event],
    { sourceReliability: 0.75, extractionConfidence: 0.8, corroboration: 0.5, recency: 0.9, evidenceSpecificity: 0.7, claimKind: "FACT" }
  ),
  claim(
    "a-7",
    "case-cold-start",
    "TERMS",
    "No prior institutional funding; no co-founder or cap table yet.",
    "DECLARED",
    [srcA_form],
    { sourceReliability: 0.65, extractionConfidence: 0.8, corroboration: 0.2, recency: 0.9, evidenceSpecificity: 0.6, claimKind: "FACT" }
  ),
  claim(
    "a-8",
    "case-cold-start",
    "DIFFERENTIATION",
    "Differentiation remains unproven beyond a weekend prototype.",
    "UNRESOLVED",
    [srcA_form],
    { sourceReliability: 0.6, extractionConfidence: 0.6, corroboration: 0.2, recency: 0.9, evidenceSpecificity: 0.4, claimKind: "ASSUMPTION" }
  ),
];

export const caseA: InvestmentCase = {
  id: "case-cold-start",
  founderIds: ["talent-a"],
  sourceChannel: "Outbound: Hackathon result + GitHub artifact",
  inboundOrOutbound: "OUTBOUND",
  status: "ACTIVATION_READY",
  thesisResult: "ELIGIBLE",
  owner: "AI Sourcing Agent",
  createdAt: iso(-2),
  decisionDeadline: iso(22),
  nextAction: "Send personalized invitation to apply and schedule a 15-minute builder call.",
  claims: claimsA,
  drivers: [
    driver(
      "FOUNDER",
      88,
      0.75,
      "IMPROVING",
      "Strong artifact and execution signal with corroboration from event and GitHub.",
      ["a-1", "a-2"],
      ["a-8"],
      ["Commercial experience", "Customer reference", "Co-founder fit"]
    ),
    driver(
      "MARKET",
      50,
      0.45,
      "INSUFFICIENT_HISTORY",
      "AI developer tooling is a plausible market; no specific buyer evidence yet.",
      ["a-6"],
      [],
      ["Buyer urgency", "Competitive map", "Market timing"]
    ),
    driver(
      "VISION_PRODUCT",
      55,
      0.45,
      "STABLE",
      "Problem statement is coherent but unvalidated with paying users.",
      ["a-5"],
      ["a-8"],
      ["User interviews", "Willingness-to-pay data"]
    ),
    driver(
      "TRACTION",
      78,
      0.68,
      "IMPROVING",
      "Inbound interest from public demo is a momentum signal, not monetized traction.",
      ["a-4"],
      [],
      ["Revenue or LOI", "Usage analytics"]
    ),
    driver(
      "DIFFERENTIATION",
      60,
      0.5,
      "STABLE",
      "Technical execution is visible; defensibility and wedge are unknown.",
      ["a-2"],
      ["a-8"],
      ["Moat analysis", "Distribution hypothesis"]
    ),
    driver(
      "VALUATION_CAP",
      50,
      0.4,
      "INSUFFICIENT_HISTORY",
      "No company or terms yet; check size and ownership cannot be assessed.",
      ["a-7"],
      [],
      ["Cap table", "Valuation expectation"]
    ),
  ],
  axes: [
    axis("FOUNDER", 88, 0.75, "IMPROVING", ["FOUNDER"]),
    axis("MARKET", 50, 0.45, "INSUFFICIENT_HISTORY", ["MARKET"]),
    axis("IDEA_MARKET", 60, 0.48, "STABLE", ["VISION_PRODUCT", "TRACTION", "DIFFERENTIATION", "VALUATION_CAP"]),
  ],
  triggeredRules: [],
  memo: memo(
    "Alex Rivera is an outbound cold-start builder (no company, no funding) flagged from a hackathon result and GitHub artifact. Strong execution signal, no commercial evidence yet.",
    [
      "A technical builder with public shipped artifacts can be converted into a pre-seed opportunity quickly.",
      "The weekend prototype is not yet a product, but it is a cheap signal to explore founder-market fit.",
    ],
    {
      strengths: ["Fast execution", "Public artifact with corroboration", "Technical depth"],
      weaknesses: ["No co-founder", "No commercial track record", "No customer evidence"],
      opportunities: ["Invite to apply", "Run structured founder assessment", "Introduce to potential users"],
      threats: ["Builder may not want to start a company", "AI dev-tool market is crowded"],
    },
    "The hackathon demo targets code-review latency for AI-assisted developer tools. Product scope is narrow and unvalidated beyond a weekend.",
    ["Inbound interest from 6+ engineering teams (unverified)", "No revenue disclosed", "No active user metrics disclosed"],
    [],
    ["Customer reference or user interview", "Co-founder plan", "Commercial intent signal"],
    "Send personalized invitation to apply; if accepted, run cold-start founder assessment within 48 hours.",
    {
      "Alex Rivera": ["a-1", "a-2", "a-3"],
      "Hackathon result": ["a-1"],
      "GitHub artifact": ["a-2"],
    }
  ),
  history: [
    {
      id: "evt-a-1",
      entityId: "case-cold-start",
      eventType: "TALENT_SIGNAL_DISCOVERED",
      effectiveAt: iso(-48),
      observedAt: iso(-50),
      sourceRefIds: ["src-a-event", "src-a-github"],
      affectedDrivers: ["FOUNDER", "TRACTION"],
      previousValues: { FOUNDER: 50, TRACTION: 50 },
      newValues: { FOUNDER: 88, TRACTION: 78 },
      explanation:
        "Hackathon result and GitHub artifact added. Founder execution signal moved to 88 with confidence 0.75; traction momentum signal moved to 78 with confidence 0.68.",
    },
  ],
  termsCheckSize: 100000,
  termsOwnershipTarget: 0.05,
  strongestEvidenceClaimIds: ["a-1", "a-2"],
};

// ===================== CASE B: Strong founder, weak current idea =====================

const srcB_ref1 = source("src-b-ref1", "REFERENCE", "Former manager reference", {
  excerpt: "Led the core inference platform team; shipped two production launches on time.",
});
const srcB_ref2 = source("src-b-ref2", "REFERENCE", "Peer reference", {
  excerpt: "Deep expertise in distributed training and inference; very strong technical judgment.",
});
const srcB_github = source("src-b-github", "GITHUB", "github.com/sokonkwo", {
  url: "https://github.com/sokonkwo",
  excerpt: "Open-source ML tooling contributions with consistent commits over 18 months.",
});
const srcB_deck = source("src-b-deck", "DECK", "PromptBridge pitch deck", { slide: 3, excerpt: "Product described as a Chrome extension for prompt templates." });
const srcB_form = source("src-b-form", "FORM", "Inbound application form", {
  excerpt: "Market is 'all prompt engineers'; no distribution plan; pre-money cap $8M.",
});

const claimsB: Claim[] = [
  claim(
    "b-1",
    "case-founder-spike",
    "TEAM",
    "Verified execution record: shipped two production AI infrastructure launches on time.",
    "VERIFIED",
    [srcB_ref1, srcB_ref2],
    { sourceReliability: 0.85, extractionConfidence: 0.85, corroboration: 0.85, recency: 0.8, evidenceSpecificity: 0.8, claimKind: "FACT" }
  ),
  claim(
    "b-2",
    "case-founder-spike",
    "TEAM",
    "Deep domain expertise in distributed training and inference systems.",
    "VERIFIED",
    [srcB_ref2, srcB_github],
    { sourceReliability: 0.85, extractionConfidence: 0.8, corroboration: 0.8, recency: 0.8, evidenceSpecificity: 0.8, claimKind: "FACT" }
  ),
  claim(
    "b-3",
    "case-founder-spike",
    "TEAM",
    "Open-source ML tooling contributions show long-term technical consistency.",
    "VERIFIED",
    [srcB_github],
    { sourceReliability: 0.85, extractionConfidence: 0.8, corroboration: 0.7, recency: 0.8, evidenceSpecificity: 0.75, claimKind: "FACT" }
  ),
  claim(
    "b-4",
    "case-founder-spike",
    "PRODUCT",
    "Current idea is a Chrome extension for prompt templates, described as a feature rather than a defensible product.",
    "DECLARED",
    [srcB_deck, srcB_form],
    { sourceReliability: 0.7, extractionConfidence: 0.8, corroboration: 0.4, recency: 0.9, evidenceSpecificity: 0.7, claimKind: "OPINION" }
  ),
  claim(
    "b-5",
    "case-founder-spike",
    "MARKET",
    "Target market is 'all prompt engineers' with no clear buyer urgency or segmentation.",
    "DECLARED",
    [srcB_deck, srcB_form],
    { sourceReliability: 0.65, extractionConfidence: 0.75, corroboration: 0.3, recency: 0.9, evidenceSpecificity: 0.5, claimKind: "ASSUMPTION" }
  ),
  claim(
    "b-6",
    "case-founder-spike",
    "DIFFERENTIATION",
    "No differentiated moat or distribution plan presented.",
    "DECLARED",
    [srcB_form],
    { sourceReliability: 0.65, extractionConfidence: 0.75, corroboration: 0.2, recency: 0.9, evidenceSpecificity: 0.5, claimKind: "ASSUMPTION" }
  ),
  claim(
    "b-7",
    "case-founder-spike",
    "TRACTION",
    "No usage or revenue evidence; product is pre-launch.",
    "DECLARED",
    [srcB_form],
    { sourceReliability: 0.65, extractionConfidence: 0.8, corroboration: 0.2, recency: 0.9, evidenceSpecificity: 0.6, claimKind: "FACT" }
  ),
  claim(
    "b-8",
    "case-founder-spike",
    "TERMS",
    "Pre-money cap of $8M with a $100K check target; ownership estimate ~1.2%.",
    "DECLARED",
    [srcB_deck],
    { sourceReliability: 0.7, extractionConfidence: 0.8, corroboration: 0.2, recency: 0.9, evidenceSpecificity: 0.8, claimKind: "FACT" }
  ),
];

export const caseB: InvestmentCase = {
  id: "case-founder-spike",
  companyId: "weak-idea-co",
  founderIds: ["founder-b"],
  sourceChannel: "Inbound application",
  inboundOrOutbound: "INBOUND",
  status: "ASSOCIATE_REVIEW",
  thesisResult: "ELIGIBLE",
  owner: "Analyst - Jordan Lee",
  createdAt: iso(-36),
  decisionDeadline: iso(12),
  nextAction: "Founder conversation focused on alternative wedge or pivot.",
  claims: claimsB,
  drivers: [
    driver(
      "FOUNDER",
      90,
      0.78,
      "IMPROVING",
      "Verified execution and domain expertise with multiple independent references and a public GitHub record.",
      ["b-1", "b-2"],
      [],
      ["Leadership at scale", "Co-founder quality"]
    ),
    driver(
      "MARKET",
      52,
      0.45,
      "STABLE",
      "Market is described broadly; no evidence of buyer urgency or segmentation.",
      ["b-5"],
      ["b-5"],
      ["Buyer interviews", "Competitive landscape"]
    ),
    driver(
      "VISION_PRODUCT",
      48,
      0.55,
      "DECLINING",
      "Current idea looks like a feature, not a defensible product or wedge.",
      ["b-4"],
      ["b-4", "b-6"],
      ["Validated wedge", "Distribution hypothesis"]
    ),
    driver(
      "TRACTION",
      55,
      0.5,
      "STABLE",
      "No usage or revenue evidence; product is pre-launch.",
      ["b-7"],
      [],
      ["Launch data", "Usage analytics"]
    ),
    driver(
      "DIFFERENTIATION",
      58,
      0.5,
      "STABLE",
      "No differentiated moat or distribution plan is visible.",
      ["b-2"],
      ["b-6"],
      ["Moat analysis", "Distribution experiments"]
    ),
    driver(
      "VALUATION_CAP",
      55,
      0.45,
      "STABLE",
      "Favorable cap relative to founder quality, but terms cannot compensate for weak idea evidence.",
      ["b-8"],
      [],
      ["Pro-rata rights", "Liquidation preference"]
    ),
  ],
  axes: [
    axis("FOUNDER", 90, 0.78, "IMPROVING", ["FOUNDER"]),
    axis("MARKET", 52, 0.45, "STABLE", ["MARKET"]),
    axis("IDEA_MARKET", 54, 0.52, "STABLE", ["VISION_PRODUCT", "TRACTION", "DIFFERENTIATION", "VALUATION_CAP"]),
  ],
  triggeredRules: ["FOUNDER: score 90 with confidence 0.78 (>=85, >=0.70) triggers associate review."],
  memo: memo(
    "PromptBridge (Sam Okonkwo) is an inbound pre-seed AI software application. Founder quality is high; the current product idea is weak and looks like a feature.",
    [
      "The founder has a rare verified execution profile in AI infrastructure.",
      "The current idea (prompt-template browser extension) is likely not the right wedge; the opportunity may be founder-led pivot discovery.",
    ],
    {
      strengths: ["Exceptional founder track record", "Deep technical domain expertise", "Open-source credibility"],
      weaknesses: ["Current idea is a feature, not a product", "No market segmentation", "No traction or differentiation"],
      opportunities: ["Pivot to a hard infrastructure wedge", "Team expansion with strong founder signal"],
      threats: ["Founder may stick to weak idea", "Market noise around prompt tooling"],
    },
    "The product is a Chrome extension for saving and sharing prompt templates. Problem importance is not validated; distribution is unclear.",
    ["No revenue disclosed", "No user metrics disclosed", "Pre-launch"],
    [],
    ["Validated wedge or pivot plan", "Market segmentation and buyer urgency", "Usage evidence or LOI"],
    "Schedule associate conversation to explore alternative wedge or pivot; do not advance to partner without a stronger idea-market hypothesis.",
    {
      "Sam Okonkwo": ["b-1", "b-2", "b-3"],
      "PromptBridge pitch deck": ["b-4", "b-8"],
    }
  ),
  history: [
    {
      id: "evt-b-1",
      entityId: "case-founder-spike",
      eventType: "FOUNDER_SPIKE_DETECTED",
      effectiveAt: iso(-30),
      observedAt: iso(-32),
      sourceRefIds: ["src-b-ref1", "src-b-ref2"],
      affectedDrivers: ["FOUNDER"],
      previousValues: { FOUNDER: 50 },
      newValues: { FOUNDER: 90 },
      explanation: "Reference checks and GitHub review confirmed high founder execution and domain ability. Score moved from 50 to 90 with confidence 0.78.",
    },
    {
      id: "evt-b-2",
      entityId: "case-founder-spike",
      eventType: "QUARTERLY_UPDATE_RECEIVED",
      effectiveAt: iso(-6),
      observedAt: iso(-8),
      sourceRefIds: ["src-b-form"],
      affectedDrivers: ["TRACTION"],
      previousValues: { TRACTION: 45 },
      newValues: { TRACTION: 55 },
      explanation:
        "Monitored case submitted a quarterly update. Traction improved from 45 to 55 because of a verified design-partner conversation, but remains below a positive spike threshold.",
    },
  ],
  termsCheckSize: 100000,
  termsOwnershipTarget: 0.05,
  termsValuationCap: 8000000,
  strongestEvidenceClaimIds: ["b-1", "b-2"],
  skepticCounterCase:
    "The founder is excellent but the current idea is a commodity browser extension. Even a strong founder can waste 18 months on a feature that no enterprise buyer will pay for. The right move is to test a pivot before any term sheet.",
};

// ===================== CASE C: Contradictory traction =====================

const srcC_deck = source("src-c-deck", "DECK", "TractionAI pitch deck", { slide: 8, excerpt: "Slide 8: Traction and go-to-market." });
const srcC_deck_s1 = source("src-c-deck-s1", "DECK", "TractionAI pitch deck", { slide: 1, excerpt: "Slide 1: Company and sector overview." });
const srcC_form = source("src-c-form", "FORM", "Inbound application form", { excerpt: "Form response: 3 design partners, no paid revenue, product launched 2 weeks ago." });
const srcC_web = source("src-c-web", "WEB", "Product launch page and third-party review", { url: "https://tractionai.example/launch", excerpt: "Product launched publicly 2 weeks ago; no pricing page visible." });
const srcC_github = source("src-c-github", "GITHUB", "github.com/tractionai", { url: "https://github.com/tractionai", excerpt: "Active repo with infrastructure code." });

const claimsC: Claim[] = [
  claim(
    "c-1",
    "case-contradictory-traction",
    "TRACTION",
    "Deck claims $200,000 ARR from 15 paying customers.",
    "DECLARED",
    [srcC_deck],
    { sourceReliability: 0.7, extractionConfidence: 0.85, corroboration: 0.2, recency: 0.9, evidenceSpecificity: 0.8, claimKind: "FACT", slide: 8 }
  ),
  claim(
    "c-2",
    "case-contradictory-traction",
    "TRACTION",
    "Form response states 3 design partners and no paid revenue.",
    "CONTRADICTED",
    [srcC_form],
    { sourceReliability: 0.75, extractionConfidence: 0.85, corroboration: 0.6, recency: 0.9, evidenceSpecificity: 0.8, claimKind: "FACT", contradictionPenalty: 0.8, contradictionOf: "c-1" }
  ),
  claim(
    "c-3",
    "case-contradictory-traction",
    "TRACTION",
    "Web evidence shows product launched 2 weeks ago, contradicting a meaningful customer base.",
    "CONTRADICTED",
    [srcC_web],
    { sourceReliability: 0.8, extractionConfidence: 0.8, corroboration: 0.7, recency: 0.95, evidenceSpecificity: 0.75, claimKind: "FACT", contradictionPenalty: 0.7, contradictionOf: "c-1" }
  ),
  claim(
    "c-4",
    "case-contradictory-traction",
    "TEAM",
    "Technical team includes distributed systems and ML infrastructure experience.",
    "VERIFIED",
    [srcC_github, srcC_form],
    { sourceReliability: 0.8, extractionConfidence: 0.8, corroboration: 0.6, recency: 0.8, evidenceSpecificity: 0.7, claimKind: "FACT" }
  ),
  claim(
    "c-5",
    "case-contradictory-traction",
    "MARKET",
    "AI infrastructure for observability; United States, pre-seed.",
    "VERIFIED",
    [srcC_deck_s1, srcC_form],
    { sourceReliability: 0.75, extractionConfidence: 0.8, corroboration: 0.5, recency: 0.9, evidenceSpecificity: 0.7, claimKind: "FACT" }
  ),
  claim(
    "c-6",
    "case-contradictory-traction",
    "DIFFERENTIATION",
    "Claimed wedge: low-latency model observability for production teams.",
    "DECLARED",
    [srcC_deck],
    { sourceReliability: 0.7, extractionConfidence: 0.75, corroboration: 0.3, recency: 0.9, evidenceSpecificity: 0.65, claimKind: "ASSUMPTION" }
  ),
  claim(
    "c-7",
    "case-contradictory-traction",
    "PRODUCT",
    "Problem statement focuses on production debugging for LLM-backed applications.",
    "DECLARED",
    [srcC_deck, srcC_form],
    { sourceReliability: 0.7, extractionConfidence: 0.8, corroboration: 0.4, recency: 0.9, evidenceSpecificity: 0.7, claimKind: "ASSUMPTION" }
  ),
  claim(
    "c-8",
    "case-contradictory-traction",
    "TERMS",
    "Deck proposes a $5M pre-money cap and a $100K check.",
    "DECLARED",
    [srcC_deck],
    { sourceReliability: 0.7, extractionConfidence: 0.8, corroboration: 0.2, recency: 0.9, evidenceSpecificity: 0.8, claimKind: "FACT" }
  ),
  claim(
    "c-9",
    "case-contradictory-traction",
    "TRACTION",
    "No verified customer reference or signed contract has been provided.",
    "UNRESOLVED",
    [srcC_form],
    { sourceReliability: 0.65, extractionConfidence: 0.8, corroboration: 0.2, recency: 0.9, evidenceSpecificity: 0.6, claimKind: "FACT" }
  ),
];

export const caseC: InvestmentCase = {
  id: "case-contradictory-traction",
  companyId: "traction-ai",
  founderIds: ["founder-c"],
  sourceChannel: "Inbound deck + company",
  inboundOrOutbound: "INBOUND",
  status: "VALIDATION_HOLD",
  thesisResult: "ELIGIBLE",
  owner: "Analyst - Jordan Lee",
  createdAt: iso(-18),
  decisionDeadline: iso(6),
  nextAction: "Resolve revenue/customer adoption contradiction with bank statement or customer references.",
  claims: claimsC,
  drivers: [
    driver(
      "FOUNDER",
      70,
      0.6,
      "STABLE",
      "Technical team signal is credible but leadership and commercial experience remain unverified.",
      ["c-4"],
      [],
      ["Leadership reference", "Prior founder experience"]
    ),
    driver(
      "MARKET",
      65,
      0.55,
      "STABLE",
      "AI infrastructure observability is a plausible market; timing and buyer urgency are not yet proven.",
      ["c-5"],
      [],
      ["Buyer urgency", "Competitive map"]
    ),
    driver(
      "VISION_PRODUCT",
      68,
      0.55,
      "STABLE",
      "Problem statement is coherent for a developer audience but lacks validation depth.",
      ["c-7"],
      [],
      ["User interviews", "Willingness-to-pay"]
    ),
    driver(
      "TRACTION",
      58,
      0.4,
      "DECLINING",
      "Deck claims high traction but form and web evidence contradict it. Trust in this driver is low.",
      ["c-1"],
      ["c-2", "c-3"],
      ["Bank statement", "Customer references", "Signed contracts"]
    ),
    driver(
      "DIFFERENTIATION",
      62,
      0.55,
      "STABLE",
      "Wedge is plausible but unproven; no evidence of defensibility or distribution.",
      ["c-6"],
      [],
      ["Moat analysis", "Distribution experiments"]
    ),
    driver(
      "VALUATION_CAP",
      55,
      0.45,
      "STABLE",
      "Favorable cap, but favorable terms cannot clear a validation hold.",
      ["c-8"],
      [],
      ["Cap table", "Liquidation preference"]
    ),
  ],
  axes: [
    axis("FOUNDER", 70, 0.6, "STABLE", ["FOUNDER"]),
    axis("MARKET", 65, 0.55, "STABLE", ["MARKET"]),
    axis("IDEA_MARKET", 60, 0.49, "STABLE", ["VISION_PRODUCT", "TRACTION", "DIFFERENTIATION", "VALUATION_CAP"]),
  ],
  validationHoldReason:
    "Deck claims $200k ARR and 15 paying customers, but the form and web evidence contradict this. The case cannot advance until the contradiction is resolved.",
  triggeredRules: [],
  memo: memo(
    "TractionAI (Priya Nair) is an inbound AI infrastructure company. Deck claims meaningful traction, but form and web evidence conflict. Case is on validation hold.",
    [
      "If the traction contradiction is resolved in the company's favor, the case could move quickly to partner review.",
      "If the contradiction stands, the case should be declined regardless of favorable terms.",
    ],
    {
      strengths: ["Technical team credibility", "Clear AI infrastructure wedge", "Favorable terms"],
      weaknesses: ["Contradicted traction claims", "No verified customer references", "Recent launch timeline conflicts with revenue"],
      opportunities: ["Resolve contradiction with strong evidence", "Expand into adjacent observability buyer"],
      threats: ["Founder may have misrepresented traction", "Market timing unclear"],
    },
    "The product targets production debugging for LLM-backed applications. Scope is focused but not yet validated with paying users.",
    [
      "Deck: $200,000 ARR and 15 paying customers (contradicted)",
      "Form: 3 design partners, no paid revenue",
      "Web: product launched 2 weeks ago",
    ],
    [
      "Deck claims $200,000 ARR from 15 paying customers",
      "Form and web evidence contradict the customer count and revenue timeline",
    ],
    [
      "Bank statement or revenue verification",
      "Customer references for the 15 claimed customers",
      "Signed contracts or LOIs",
      "Cap table and ownership details",
    ],
    "Request bank statement or 2-3 customer references to resolve the traction contradiction before any partner decision.",
    {
      "TractionAI deck": ["c-1", "c-8"],
      "Form response": ["c-2", "c-9"],
      "Web evidence": ["c-3"],
    }
  ),
  history: [
    {
      id: "evt-c-1",
      entityId: "case-contradictory-traction",
      eventType: "CONTRADICTION_DETECTED",
      effectiveAt: iso(-12),
      observedAt: iso(-14),
      sourceRefIds: ["src-c-deck", "src-c-form", "src-c-web"],
      affectedDrivers: ["TRACTION"],
      previousValues: { TRACTION: 72 },
      newValues: { TRACTION: 58 },
      explanation:
        "Validator cross-referenced deck claims with form and web evidence. Traction driver downgraded from 72 to 58 and confidence reduced due to unresolved contradiction.",
    },
  ],
  termsCheckSize: 100000,
  termsOwnershipTarget: 0.05,
  termsValuationCap: 5000000,
  strongestEvidenceClaimIds: ["c-4", "c-5"],
  skepticCounterCase:
    "The most likely explanation is that the deck overstates traction. A product that launched two weeks ago is unlikely to have 15 paying customers and $200k ARR. If the founder cannot produce evidence, this is a pass regardless of the cap.",
};

export const DEMO_CASES: InvestmentCase[] = [caseA, caseB, caseC];

export const TALENT_SIGNALS: TalentSignal[] = [
  {
    id: "talent-a",
    person: DEMO_PEOPLE["talent-a"].name,
    currentProject: "ml-code-review (RAG code-review prototype)",
    artifactUrl: "https://github.com/arivera/ml-code-review",
    sourceChannel: "Hackathon result + GitHub",
    thesisTags: ["AI Infrastructure", "Developer Tools", "Pre-seed", "Germany"],
    strongestSignal: "Building and execution signal: 88",
    signalConfidence: 0.75,
    signalDate: iso(-50),
    momentumTrend: "IMPROVING",
    status: "ACTIVATION_READY",
    whyAppeared: "Won a technical execution prize at a thesis-relevant hackathon; GitHub artifact corroborates the signal.",
    caseId: "case-cold-start",
  },
];

export const DECK_EXTRACTIONS: Record<string, DeckExtractionResult> = {
  "case-contradictory-traction": {
    slides: [
      {
        slide: 1,
        title: "TractionAI",
        text: "AI infrastructure observability for production LLM applications. Pre-seed, United States.",
        claims: [
          { category: "MARKET", text: "AI infrastructure observability for production LLM applications.", claimKind: "ASSUMPTION", extractionConfidence: 0.75 },
          { category: "TERMS", text: "Pre-seed stage, United States.", claimKind: "FACT", extractionConfidence: 0.85 },
        ],
      },
      {
        slide: 2,
        title: "Problem",
        text: "Engineering teams lack production debugging for LLM-backed services.",
        claims: [
          { category: "PRODUCT", text: "Engineering teams lack production debugging for LLM-backed services.", claimKind: "ASSUMPTION", extractionConfidence: 0.7 },
        ],
      },
      {
        slide: 3,
        title: "Solution",
        text: "Low-latency tracing and replay for model calls.",
        claims: [
          { category: "DIFFERENTIATION", text: "Low-latency tracing and replay for model calls.", claimKind: "ASSUMPTION", extractionConfidence: 0.7 },
        ],
      },
      {
        slide: 4,
        title: "Team",
        text: "Technical founder with distributed systems and ML infrastructure experience.",
        claims: [
          { category: "TEAM", text: "Technical founder with distributed systems and ML infrastructure experience.", claimKind: "FACT", extractionConfidence: 0.8 },
        ],
      },
      {
        slide: 5,
        title: "Market",
        text: "Growing market for LLM ops and observability tooling.",
        claims: [
          { category: "MARKET", text: "Growing market for LLM ops and observability tooling.", claimKind: "PROJECTION", extractionConfidence: 0.6 },
        ],
      },
      {
        slide: 6,
        title: "Product",
        text: "Cloud dashboard and SDK for model-call tracing.",
        claims: [
          { category: "PRODUCT", text: "Cloud dashboard and SDK for model-call tracing.", claimKind: "ASSUMPTION", extractionConfidence: 0.75 },
        ],
      },
      {
        slide: 7,
        title: "Go-to-market",
        text: "Bottom-up developer adoption with enterprise sales overlay.",
        claims: [
          { category: "DIFFERENTIATION", text: "Bottom-up developer adoption with enterprise sales overlay.", claimKind: "ASSUMPTION", extractionConfidence: 0.65 },
        ],
      },
      {
        slide: 8,
        title: "Traction",
        text: "$200,000 ARR from 15 paying customers. Product launched 6 months ago.",
        claims: [
          { category: "TRACTION", text: "$200,000 ARR from 15 paying customers.", claimKind: "FACT", extractionConfidence: 0.85 },
          { category: "TRACTION", text: "Product launched 6 months ago.", claimKind: "FACT", extractionConfidence: 0.75 },
        ],
      },
      {
        slide: 9,
        title: "Terms",
        text: "Raising $500K at a $5M pre-money cap. $100K minimum check.",
        claims: [
          { category: "TERMS", text: "Raising $500K at a $5M pre-money cap.", claimKind: "FACT", extractionConfidence: 0.8 },
          { category: "TERMS", text: "$100K minimum check.", claimKind: "FACT", extractionConfidence: 0.8 },
        ],
      },
    ],
    missingSections: ["Financial projections", "Detailed cap table", "Customer reference list"],
    unreadableSlides: [],
  },
  "case-founder-spike": {
    slides: [
      {
        slide: 1,
        title: "PromptBridge",
        text: "A Chrome extension for saving and sharing prompt templates. Pre-seed, United States.",
        claims: [
          { category: "PRODUCT", text: "A Chrome extension for saving and sharing prompt templates.", claimKind: "FACT", extractionConfidence: 0.85 },
        ],
      },
      {
        slide: 2,
        title: "Problem",
        text: "Prompt engineers waste time rewriting prompts.",
        claims: [
          { category: "PRODUCT", text: "Prompt engineers waste time rewriting prompts.", claimKind: "ASSUMPTION", extractionConfidence: 0.7 },
        ],
      },
      {
        slide: 3,
        title: "Product",
        text: "Browser extension with template library and team sharing.",
        claims: [
          { category: "PRODUCT", text: "Browser extension with template library and team sharing.", claimKind: "ASSUMPTION", extractionConfidence: 0.75 },
        ],
      },
      {
        slide: 4,
        title: "Market",
        text: "All prompt engineers and AI teams.",
        claims: [
          { category: "MARKET", text: "All prompt engineers and AI teams.", claimKind: "ASSUMPTION", extractionConfidence: 0.65 },
        ],
      },
      {
        slide: 5,
        title: "Traction",
        text: "Pre-launch; 50 waitlist signups.",
        claims: [
          { category: "TRACTION", text: "Pre-launch; 50 waitlist signups.", claimKind: "FACT", extractionConfidence: 0.75 },
        ],
      },
      {
        slide: 6,
        title: "Terms",
        text: "Raising $750K at an $8M pre-money cap. $100K check.",
        claims: [
          { category: "TERMS", text: "Raising $750K at an $8M pre-money cap.", claimKind: "FACT", extractionConfidence: 0.8 },
          { category: "TERMS", text: "$100K check.", claimKind: "FACT", extractionConfidence: 0.8 },
        ],
      },
    ],
    missingSections: ["Distribution plan", "Competitive moat", "Customer interview evidence"],
    unreadableSlides: [],
  },
  "case-cold-start": {
    slides: [
      {
        slide: 1,
        title: "ML Code Review",
        text: "RAG-based code review prototype from LLM Hack Berlin.",
        claims: [
          { category: "PRODUCT", text: "RAG-based code review prototype.", claimKind: "FACT", extractionConfidence: 0.85 },
        ],
      },
      {
        slide: 2,
        title: "Demo",
        text: "48-hour build with tests and architecture notes.",
        claims: [
          { category: "TEAM", text: "48-hour build with tests and architecture notes.", claimKind: "FACT", extractionConfidence: 0.8 },
        ],
      },
      {
        slide: 3,
        title: "Next steps",
        text: "Looking for design partners and a co-founder.",
        claims: [
          { category: "TERMS", text: "No company formed; seeking design partners and co-founder.", claimKind: "FACT", extractionConfidence: 0.8 },
        ],
      },
    ],
    missingSections: ["Market sizing", "Business model", "Go-to-market"],
    unreadableSlides: [],
  },
};

export function getDemoCase(id: string): InvestmentCase | undefined {
  return DEMO_CASES.find((c) => c.id === id);
}

export function getDemoDeck(caseId: string): DeckExtractionResult | undefined {
  return DECK_EXTRACTIONS[caseId];
}

export function getDemoPerson(id: string): { name: string; role: string; location: string; bio: string; demoLabel?: boolean } | undefined {
  return DEMO_PEOPLE[id];
}

export function getDemoCompany(id: string): { name: string; sector: string; stage: string; geography: string; demoLabel?: boolean } | undefined {
  return DEMO_COMPANIES[id];
}
