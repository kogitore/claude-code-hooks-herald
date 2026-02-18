import { describe, test, expect } from "bun:test";
import { handleNotification } from "../../handlers/notification";
import type { HookContext } from "../../lib/types";

describe("handleNotification", () => {
  test("returns Notification audio type", () => {
    const ctx: HookContext = { eventType: "Notification", payload: {}, decisionApi: null };
    const r = handleNotification(ctx);
    expect(r.audioType).toBe("Notification");
    expect(r.continueValue).toBe(true);
  });
});
