import { describe, test, expect } from "bun:test";
import { handleStop, handleSubagentStop } from "../../handlers/stop";
import type { HookContext } from "../../lib/types";

describe("handleStop", () => {
  test("uses event type as audio type for Stop", () => {
    const ctx: HookContext = { eventType: "Stop", payload: {}, decisionApi: null };
    const r = handleStop(ctx);
    expect(r.audioType).toBe("Stop");
    expect(r.continueValue).toBe(true);
  });

  test("uses event type as audio type for SubagentStop", () => {
    const ctx: HookContext = { eventType: "SubagentStop", payload: {}, decisionApi: null };
    const r = handleSubagentStop(ctx);
    expect(r.audioType).toBe("SubagentStop");
  });
});
