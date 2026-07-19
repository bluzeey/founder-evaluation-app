import { describe, it, expect } from "vitest";
import { applyEvent } from "@/engine/stateMachine";
import { caseB } from "@/data/demoCases";

describe("history", () => {
  it("preserves the previous snapshot when an event is applied", () => {
    const original = JSON.parse(JSON.stringify(caseB));
    const event = {
      id: "evt-history-test",
      entityId: caseB.id,
      eventType: "QUARTERLY_UPDATE",
      effectiveAt: new Date().toISOString(),
      observedAt: new Date().toISOString(),
      sourceRefIds: ["src-b-form"],
      affectedDrivers: ["TRACTION"] as import("@/domain/types").DriverKey[],
      previousValues: { TRACTION: 55 },
      newValues: { TRACTION: 70 },
      explanation: "Test traction update",
    };
    const updated = applyEvent(caseB, event);

    // Original fixture must remain unchanged (immutable snapshot).
    expect(JSON.stringify(caseB)).toEqual(JSON.stringify(original));

    // Updated case contains the new event and a changed history.
    expect(updated.history).toContainEqual(event);
    expect(updated.history?.length).toBeGreaterThan(original.history?.length ?? 0);
  });
});
