import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { ReactElement } from "react";
import { ManualAIAction, ManualModeIndicator } from "./ManualAI";

// Actual button handlers and polling, using a hook harness without a browser.
const hooks = vi.hoisted(() => ({ values: [] as unknown[], cursor: 0,
  poll: null as null | (() => Promise<void>), interval: 0 }));
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
    useEffect: () => {},
  };
});
vi.mock("@/hooks/useAdaptivePolling", () => ({
  useAdaptivePolling: (callback: () => Promise<void>, interval: number) => {
    hooks.poll = callback; hooks.interval = interval;
  },
}));

type ButtonTree = ReactElement<{ children: [ReactElement<{ onClick: () => Promise<void>; disabled: boolean }> ] }>;
function view(run: () => Promise<{ task_id?: string; status: string }>) {
  hooks.cursor = 0;
  return ManualAIAction({ label: "Run AI estimate", run }) as ButtonTree;
}
beforeEach(() => {
  hooks.values = []; hooks.cursor = 0; hooks.poll = null; hooks.interval = 0;
  vi.restoreAllMocks(); vi.stubGlobal("fetch", vi.fn());
});

describe("manual AI controls", () => {
  it("viewing controls does not run AI or poll; shows manual mode", () => {
    const run = vi.fn(); const tree = view(run);
    expect(renderToStaticMarkup(tree)).toContain("Run AI estimate");
    expect(renderToStaticMarkup(ManualModeIndicator())).toContain("AI manual mode");
    expect(hooks.interval).toBe(0);
    expect(run).not.toHaveBeenCalled(); expect(fetch).not.toHaveBeenCalled();
  });
  it("a click queues once and displays progress and completion", async () => {
    const run = vi.fn().mockResolvedValue({ task_id: "manual-123", status: "queued" });
    let tree = view(run);
    await tree.props.children[0].props.onClick();
    await tree.props.children[0].props.onClick();
    expect(run).toHaveBeenCalledTimes(1);
    tree = view(run);
    expect(tree.props.children[0].props.disabled).toBe(true);
    expect(renderToStaticMarkup(tree)).toContain("AI queued");
    expect(hooks.interval).toBe(3000);
    vi.mocked(fetch).mockResolvedValue({ ok: true, json: async () => ({ status: "running" }) } as Response);
    await hooks.poll?.(); tree = view(run);
    expect(renderToStaticMarkup(tree)).toContain("AI running");
    expect(fetch).toHaveBeenCalledWith("/api/v1/ai/tasks/manual-123", { credentials: "include" });
    vi.mocked(fetch).mockResolvedValue({ ok: true, json: async () => ({ status: "completed" }) } as Response);
    await hooks.poll?.(); tree = view(run);
    expect(renderToStaticMarkup(tree)).toContain("AI completed");
    expect(tree.props.children[0].props.disabled).toBe(false);
    expect(hooks.interval).toBe(0); expect(run).toHaveBeenCalledTimes(1);
  });
  it("shows queue and task errors without automatically retrying AI", async () => {
    const run = vi.fn().mockRejectedValueOnce(new Error("Queue unavailable"))
      .mockResolvedValueOnce({ task_id: "manual-456", status: "queued" });
    let tree = view(run); await tree.props.children[0].props.onClick(); tree = view(run);
    expect(renderToStaticMarkup(tree)).toContain("Queue unavailable");
    expect(tree.props.children[0].props.disabled).toBe(false);
    await tree.props.children[0].props.onClick(); tree = view(run);
    vi.mocked(fetch).mockResolvedValue({ ok: true, json: async () => ({ status: "failed", error: "Provider unavailable" }) } as Response);
    await hooks.poll?.(); tree = view(run);
    expect(renderToStaticMarkup(tree)).toContain("Provider unavailable");
    expect(hooks.interval).toBe(0); expect(run).toHaveBeenCalledTimes(2);
  });
});
