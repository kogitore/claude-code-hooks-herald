import { describe, test, expect } from "bun:test";
import { handlePostToolUse } from "../../handlers/post-tool-use";
import type { HookContext } from "../../lib/types";

describe("handlePostToolUse", () => {
  test("suppresses audio on success", () => {
    const ctx: HookContext = {
      eventType: "PostToolUse",
      payload: { tool: "Bash", result: { exitCode: 0, success: true } },
      decisionApi: null,
    };
    const r = handlePostToolUse(ctx);
    expect(r.continueValue).toBe(true);
    expect(r.suppressAudio).toBe(true);
  });

  test("alerts on non-zero exit code", () => {
    const ctx: HookContext = {
      eventType: "PostToolUse",
      payload: { tool: "Bash", result: { exitCode: 1 } },
      decisionApi: null,
    };
    const r = handlePostToolUse(ctx);
    expect(r.continueValue).toBe(false);
    expect(r.audioType).toBe("PostToolUse");
  });

  test("alerts on error message", () => {
    const ctx: HookContext = {
      eventType: "PostToolUse",
      payload: { tool: "Bash", result: { error: "something failed" } },
      decisionApi: null,
    };
    const r = handlePostToolUse(ctx);
    expect(r.audioType).toBe("PostToolUse");
  });

  test("handles missing result gracefully", () => {
    const ctx: HookContext = {
      eventType: "PostToolUse",
      payload: { tool: "Bash" },
      decisionApi: null,
    };
    const r = handlePostToolUse(ctx);
    expect(r.continueValue).toBe(true);
  });
});
