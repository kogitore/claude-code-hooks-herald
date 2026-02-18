import { describe, test, expect } from "bun:test";
import { handlePreToolUse } from "../../handlers/pre-tool-use";
import type { HookContext } from "../../lib/types";

describe("handlePreToolUse", () => {
  test("allows safe command", () => {
    const ctx: HookContext = {
      eventType: "PreToolUse",
      payload: { tool: "Bash", toolInput: { command: "echo hello" } },
      decisionApi: null,
    };
    const r = handlePreToolUse(ctx);
    expect(r.continueValue).toBe(true);
    expect(r.suppressAudio).toBe(true);
    expect(r.decisionPayload?.permissionDecision).toBe("allow");
  });

  test("denies dangerous command", () => {
    const ctx: HookContext = {
      eventType: "PreToolUse",
      payload: { tool: "Bash", toolInput: { command: "rm -rf /" } },
      decisionApi: null,
    };
    const r = handlePreToolUse(ctx);
    expect(r.continueValue).toBe(false);
    expect(r.audioType).toBe("PreToolUse");
    expect(r.decisionPayload?.permissionDecision).toBe("deny");
  });

  test("handles missing tool input", () => {
    const ctx: HookContext = {
      eventType: "PreToolUse",
      payload: { tool: "Bash" },
      decisionApi: null,
    };
    const r = handlePreToolUse(ctx);
    expect(r.continueValue).toBe(true);
  });

  test("handles string tool input", () => {
    const ctx: HookContext = {
      eventType: "PreToolUse",
      payload: { tool: "Bash", toolInput: '{"command":"ls"}' },
      decisionApi: null,
    };
    const r = handlePreToolUse(ctx);
    expect(r.continueValue).toBe(true);
    expect(r.suppressAudio).toBe(true);
  });

  test("asks on invalid JSON tool input", () => {
    const ctx: HookContext = {
      eventType: "PreToolUse",
      payload: { tool: "Bash", toolInput: "not-json{" },
      decisionApi: null,
    };
    const r = handlePreToolUse(ctx);
    expect(r.audioType).toBe("PreToolUse");
  });
});
