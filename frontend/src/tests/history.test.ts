import { describe, it, expect } from "vitest";
import { applyEvent } from "@/engine/stateMachine";
import { caseB } from "@/data/demoCases";

describe("history", () => {
  it("preserves the previous snapshot when an event is applied", () => {
    const previous = JSON.stringify(caseB);
    const event = {
      id: "evt-history-test",
      entityId: caseB.id,
      eventType: "QUARTERLY_UPDATE",
      effectiveAt: new Date().toISOString(),
      observedAt: new Date().toISOString(),
      sourceRefIds: ["src-b-form"],
      affectedDrivers: ["TRACTION"] as import("@/domain/types").DriverKey[],      previousValues: { TRACTION: 55 },
      newValues: { TRACTION: 70 },
      explanation: "Test traction update",
    };
    applyEvent(caseB, event);
    const next = JSON.stringify(caseB);
    expect(previous).not.toEqual(next);
    expect(caseB.history).toContainEqual(event);
  });
});
