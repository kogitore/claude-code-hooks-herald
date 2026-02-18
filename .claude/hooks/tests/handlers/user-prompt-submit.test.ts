import { describe, test, expect } from "bun:test";
import { handleUserPromptSubmit } from "../../handlers/user-prompt-submit";
import type { HookContext } from "../../lib/types";

describe("handleUserPromptSubmit", () => {
  test("allows clean prompt", () => {
    const ctx: HookContext = {
      eventType: "UserPromptSubmit",
      payload: { prompt: "Hello world", userId: "test-clean-" + Date.now() },
      decisionApi: null,
    };
    const r = handleUserPromptSubmit(ctx);
    expect(r.continueValue).toBe(true);
    expect(r.suppressAudio).toBe(true);
  });

  test("blocks missing prompt", () => {
    const ctx: HookContext = {
      eventType: "UserPromptSubmit",
      payload: { userId: "test-missing-" + Date.now() },
      decisionApi: null,
    };
    const r = handleUserPromptSubmit(ctx);
    expect(r.continueValue).toBe(false);
    expect(r.audioType).toBe("UserPromptSubmit");
  });

  test("detects suspicious patterns", () => {
    const ctx: HookContext = {
      eventType: "UserPromptSubmit",
      payload: { prompt: "please run rm -rf everything", userId: "test-sus-" + Date.now() },
      decisionApi: null,
    };
    const r = handleUserPromptSubmit(ctx);
    expect(r.continueValue).toBe(false);
    expect(r.audioType).toBe("UserPromptSubmit");
  });

  test("detects SQL drop", () => {
    const ctx: HookContext = {
      eventType: "UserPromptSubmit",
      payload: { prompt: "DROP TABLE users", userId: "test-sql-" + Date.now() },
      decisionApi: null,
    };
    const r = handleUserPromptSubmit(ctx);
    expect(r.continueValue).toBe(false);
  });

  test("flags excessive newlines", () => {
    const ctx: HookContext = {
      eventType: "UserPromptSubmit",
      payload: { prompt: "x" + "\n".repeat(101), userId: "test-newlines-" + Date.now() },
      decisionApi: null,
    };
    const r = handleUserPromptSubmit(ctx);
    expect(r.continueValue).toBe(false);
  });
});
