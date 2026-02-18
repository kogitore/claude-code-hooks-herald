import { describe, test, expect } from "bun:test";
import { handleSessionStart } from "../../handlers/session-start";
import { handleSessionEnd } from "../../handlers/session-end";
import type { HookContext } from "../../lib/types";

describe("handleSessionStart", () => {
  test("returns SessionStart audio type", () => {
    const ctx: HookContext = {
      eventType: "SessionStart",
      payload: { sessionId: "test-session-unit" },
      decisionApi: null,
    };
    const r = handleSessionStart(ctx);
    expect(r.audioType).toBe("SessionStart");
    expect(r.continueValue).toBe(true);
  });

  test("sets hookSpecificOutput with session info", () => {
    const ctx: HookContext = {
      eventType: "SessionStart",
      payload: { sessionId: "test-unit-hso", start_time: "2026-01-01T00:00:00Z" },
      decisionApi: null,
    };
    const r = handleSessionStart(ctx);
    const hso = r.response.hookSpecificOutput as Record<string, unknown>;
    expect(hso).toBeDefined();
    expect(hso.hookEventName).toBe("SessionStart");
    const addlCtx = JSON.parse(hso.additionalContext as string);
    expect(addlCtx.sessionId).toBe("test-unit-hso");
  });

  test("never blocks on error", () => {
    const ctx: HookContext = {
      eventType: "SessionStart",
      payload: null as any,
      decisionApi: null,
    };
    const r = handleSessionStart(ctx);
    expect(r.continueValue).toBe(true);
  });
});

describe("handleSessionEnd", () => {
  test("returns SessionEnd audio type", () => {
    const ctx: HookContext = {
      eventType: "SessionEnd",
      payload: { sessionId: "test-session-end" },
      decisionApi: null,
    };
    const r = handleSessionEnd(ctx);
    expect(r.audioType).toBe("SessionEnd");
    expect(r.continueValue).toBe(true);
  });

  test("sets hookSpecificOutput with end info", () => {
    const ctx: HookContext = {
      eventType: "SessionEnd",
      payload: { sessionId: "test-end-hso", end_time: "2026-01-01T01:00:00Z", duration: 3600 },
      decisionApi: null,
    };
    const r = handleSessionEnd(ctx);
    const hso = r.response.hookSpecificOutput as Record<string, unknown>;
    expect(hso).toBeDefined();
    expect(hso.hookEventName).toBe("SessionEnd");
    const addlCtx = JSON.parse(hso.additionalContext as string);
    expect(addlCtx.sessionId).toBe("test-end-hso");
    expect(addlCtx.durationSeconds).toBe(3600);
  });
});
