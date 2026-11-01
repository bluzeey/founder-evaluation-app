import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { ReactElement } from "react";
import { ManualAIAction, ManualModeIndicator } from "./ManualAI";

// Exercise real handlers/effects with deterministic hooks, without a browser.
const hooks = vi.hoisted(() => ({ values: [] as unknown[], cursor: 0,
  effects: [] as (() => void)[], polls: [] as { callback: () => Promise<void>; interval: number }[] }));
vi.mock("react", async (original) => {
  const actual = await original<typeof import("react")>();
  return { ...actual,
    useState: (initial: unknown) => {
      const index = hooks.cursor++;
      if (!(index in hooks.values)) hooks.values[index] = initial;
      return [hooks.values[index], (value: unknown) => { hooks.values[index] = value; }];
    },
    useRef: (initial: unknown) => {
      const index = hooks.cursor++;
      if (!(index in hooks.values)) hooks.values[index] = { current: initial };
      return hooks.values[index];
    },
    useEffect: (effect: () => void | (() => void), deps?: unknown[]) => {
      const index = hooks.cursor++;
      const previous = hooks.values[index] as { deps?: unknown[]; cleanup?: () => void } | undefined;
      if (!previous || !deps || deps.some((value, i) => value !== previous.deps?.[i])) {
        hooks.effects.push(() => {
          previous?.cleanup?.();
          hooks.values[index] = { deps, cleanup: effect() };
        });
      }
    },
  };
});
vi.mock("@/hooks/useAdaptivePolling", () => ({
  useAdaptivePolling: (callback: () => Promise<void>, interval: number) => {
    hooks.polls.push({ callback, interval });
  },
}));

type Run = () => Promise<{ task_id?: string; status: string }>;
type ButtonTree = ReactElement<{ children: [ReactElement<{ onClick: () => Promise<void>; disabled: boolean }> ] }>;
function view(run: Run, disabled = false) {
  hooks.cursor = 0;
  hooks.polls = [];
  return ManualAIAction({ label: "Run AI estimate", run, disabled }) as ButtonTree;
}
const button = (tree: ButtonTree) => tree.props.children[0].props;
const response = (body: unknown, status = 200) => ({ ok: status >= 200 && status < 300, status,
  json: async () => body }) as Response;
async function effects() {
  for (const effect of hooks.effects.splice(0)) effect();
  await new Promise((resolve) => setImmediate(resolve));
}
async function configured(run: Run) {
  view(run);
  await effects();
  return view(run);
}
beforeEach(() => {
  hooks.values = []; hooks.cursor = 0; hooks.effects = []; hooks.polls = [];
  vi.restoreAllMocks();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ enabled: true, mode: "manual" })));
});

describe("manual AI readiness controls", () => {
  it("mount reads only local readiness and starts no paid work or task polling", async () => {
    const run = vi.fn(); const tree = view(run);
    expect(button(tree).disabled).toBe(true);
    expect(renderToStaticMarkup(tree)).toContain("Checking AI setup");
    expect(renderToStaticMarkup(ManualModeIndicator())).toContain("AI manual mode");
    await effects();
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith("/api/v1/ai/config", { credentials: "include" });
    expect(hooks.polls[0].interval).toBe(30000);
    expect(hooks.polls[1].interval).toBe(0);
    expect(run).not.toHaveBeenCalled();
  });

  it("missing configuration disables Run, shows setup pending and offers no key input", async () => {
    vi.mocked(fetch).mockResolvedValue(response({ enabled: false, mode: "manual", message: "AI setup pending" }));
    const run = vi.fn(); let tree = await configured(run);
    expect(button(tree).disabled).toBe(true);
    expect(renderToStaticMarkup(tree)).toContain("AI setup pending");
    expect(renderToStaticMarkup(tree)).not.toContain("<input");
    await button(tree).onClick();
    await hooks.polls[0].callback(); tree = view(run);
    expect(run).not.toHaveBeenCalled();
    expect(button(tree).disabled).toBe(true);
    expect(hooks.polls[1].interval).toBe(0);
    expect(vi.mocked(fetch).mock.calls.every(([url]) => url === "/api/v1/ai/config")).toBe(true);
  });

  it.each([{}, null, { enabled: "true", mode: "manual" }, { enabled: true, mode: "automatic" }])(
    "fails closed for invalid readiness %j", async (config) => {
      vi.mocked(fetch).mockResolvedValue(response(config));
      const run = vi.fn(); const tree = await configured(run);
      expect(button(tree).disabled).toBe(true);
      expect(renderToStaticMarkup(tree)).toContain("AI setup pending");
      await button(tree).onClick();
      expect(run).not.toHaveBeenCalled();
    },
  );

  it("a failed readiness read stays pending and a later read only enables the button", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error("Unavailable"));
    const run = vi.fn(); let tree = await configured(run);
    expect(renderToStaticMarkup(tree)).toContain("AI setup pending");
    expect(button(tree).disabled).toBe(true);
    await hooks.polls[0].callback(); tree = view(run);
    expect(button(tree).disabled).toBe(false);
    expect(run).not.toHaveBeenCalled();
  });

  it("a click queues once and displays progress and completion", async () => {
    const run = vi.fn().mockResolvedValue({ task_id: "manual-123", status: "queued" });
    let tree = await configured(run);
    await button(tree).onClick();
    await button(tree).onClick();
    expect(run).toHaveBeenCalledTimes(1);
    tree = view(run);
    expect(button(tree).disabled).toBe(true);
    expect(renderToStaticMarkup(tree)).toContain("AI queued");
    expect(hooks.polls[1].interval).toBe(3000);
    vi.mocked(fetch).mockResolvedValueOnce(response({ status: "running" }));
    await hooks.polls[1].callback(); tree = view(run);
    expect(renderToStaticMarkup(tree)).toContain("AI running");
    expect(fetch).toHaveBeenCalledWith("/api/v1/ai/tasks/manual-123", { credentials: "include" });
    vi.mocked(fetch).mockResolvedValueOnce(response({ status: "completed" }));
    await hooks.polls[1].callback(); tree = view(run);
    expect(renderToStaticMarkup(tree)).toContain("AI completed");
    expect(button(tree).disabled).toBe(false);
    expect(hooks.polls[1].interval).toBe(0); expect(run).toHaveBeenCalledTimes(1);
  });

  it("shows queue and task errors without automatically retrying AI", async () => {
    const run = vi.fn().mockRejectedValueOnce(new Error("Queue unavailable"))
      .mockResolvedValueOnce({ task_id: "manual-456", status: "queued" });
    let tree = await configured(run); await button(tree).onClick(); tree = view(run);
    expect(renderToStaticMarkup(tree)).toContain("Queue unavailable");
    expect(button(tree).disabled).toBe(false);
    await button(tree).onClick(); tree = view(run);
    vi.mocked(fetch).mockResolvedValueOnce(response({ status: "failed", error: "Provider unavailable" }));
    await hooks.polls[1].callback(); tree = view(run);
    expect(renderToStaticMarkup(tree)).toContain("Provider unavailable");
    expect(hooks.polls[1].interval).toBe(0); expect(run).toHaveBeenCalledTimes(2);
  });

  it("a setup-pending 503 during submission disables Run with a benign message", async () => {
    const run = vi.fn().mockRejectedValue(new Error("AI setup pending"));
    let tree = await configured(run); await button(tree).onClick(); tree = view(run);
    expect(button(tree).disabled).toBe(true);
    expect(renderToStaticMarkup(tree)).toContain("AI setup pending");
    expect(renderToStaticMarkup(tree)).not.toContain('role="alert"');
    expect(hooks.polls[1].interval).toBe(0);
    await button(tree).onClick();
    expect(run).toHaveBeenCalledTimes(1);
  });

  it("readiness going offline preserves progress tracking for the existing task", async () => {
    const run = vi.fn().mockResolvedValue({ task_id: "manual-789", status: "queued" });
    let tree = await configured(run); await button(tree).onClick(); tree = view(run);
    vi.mocked(fetch).mockResolvedValueOnce(response({ enabled: false, mode: "manual" }));
    await hooks.polls[0].callback(); tree = view(run);
    expect(button(tree).disabled).toBe(true);
    expect(hooks.polls[1].interval).toBe(3000);
    vi.mocked(fetch).mockResolvedValueOnce(response({ status: "completed" }));
    await hooks.polls[1].callback(); tree = view(run);
    expect(renderToStaticMarkup(tree)).toContain("AI completed");
    expect(renderToStaticMarkup(tree)).toContain("AI setup pending");
    expect(button(tree).disabled).toBe(true);
    expect(run).toHaveBeenCalledTimes(1);
  });
});
