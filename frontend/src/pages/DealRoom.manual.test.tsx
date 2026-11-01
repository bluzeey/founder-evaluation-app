import { describe, expect, it, vi } from "vitest";
import DealRoom from "./DealRoom";
import { api } from "@/api/client";

const hooks = vi.hoisted(() => ({ values: [] as unknown[], cursor: 0, effects: [] as (() => void)[] }));
vi.mock("react", async (original) => ({
  ...await original<typeof import("react")>(),
  useState: (initial: unknown) => {
    const index = hooks.cursor++;
    if (!(index in hooks.values)) hooks.values[index] = initial;
    return [hooks.values[index], (value: unknown) => { hooks.values[index] = value; }];
  },
  useRef: (value: unknown) => ({ current: value }),
  useEffect: (effect: () => void) => { hooks.effects.push(effect); },
}));
vi.mock("react-router-dom", async (original) => ({
  ...await original<typeof import("react-router-dom")>(), useParams: () => ({ caseId: "opp_manual" }),
}));
vi.mock("@/hooks/useAdaptivePolling", () => ({ useAdaptivePolling: () => {} }));
vi.mock("@/api/client", () => ({ invalidateCache: vi.fn(), api: {
  opportunities: { get: vi.fn().mockResolvedValue({ opportunity_id: "opp_manual", founder_id: "fnd_manual" }),
    diligence: vi.fn().mockResolvedValue([]) },
  founders: { get: vi.fn().mockResolvedValue({ id: "fnd_manual", enrichment_policy: "AUTO" }),
    score: vi.fn().mockResolvedValue({ overall_confidence: 0 }),
    screeningProfile: vi.fn().mockResolvedValue(null), enrich: vi.fn(), estimate: vi.fn() },
} }));

describe("DealRoom manual AI", () => {
  it("opening a legacy AUTO cold-start founder never starts enrichment or estimation", async () => {
    hooks.values = []; hooks.cursor = 0; hooks.effects = [];
    DealRoom();
    for (const effect of hooks.effects) effect();
    await new Promise((resolve) => setImmediate(resolve));
    expect(api.opportunities.diligence).toHaveBeenCalledWith("opp_manual");
    expect(api.founders.get).toHaveBeenCalledWith("fnd_manual");
    expect(api.founders.screeningProfile).toHaveBeenCalled();
    expect(api.founders.enrich).not.toHaveBeenCalled();
    expect(api.founders.estimate).not.toHaveBeenCalled();
  });
});
