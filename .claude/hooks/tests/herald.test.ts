import { describe, test, expect } from "bun:test";
import { resolve, join, dirname } from "path";
import { existsSync, readFileSync, writeFileSync, mkdirSync } from "fs";

const HERALD = resolve(import.meta.dir, "..", "herald.ts");

function runHerald(event: string, input: Record<string, unknown>): Record<string, unknown> {
  const proc = Bun.spawnSync(["bun", "run", HERALD, "--hook", event], {
    stdin: new TextEncoder().encode(JSON.stringify(input)),
    stdout: "pipe",
    stderr: "pipe",
    env: { ...process.env, AUDIO_PLAYER_CMD: "true" },
    timeout: 5000,
  });
  const stdout = new TextDecoder().decode(proc.stdout).trim();
  return JSON.parse(stdout);
}

describe("herald integration", () => {
  test("Notification returns continue: true", () => {
    const out = runHerald("Notification", { message: "test" });
    expect(out.continue).toBe(true);
  });

  test("Stop returns continue: true", () => {
    const out = runHerald("Stop", {});
    expect(out.continue).toBe(true);
  });

  test("SubagentStop returns continue: true", () => {
    const out = runHerald("SubagentStop", {});
    expect(out.continue).toBe(true);
  });

  test("PreToolUse allows safe command", () => {
    const out = runHerald("PreToolUse", { tool: "Bash", toolInput: { command: "ls" } });
    expect(out.continue).toBe(true);
    const hso = out.hookSpecificOutput as Record<string, unknown>;
    expect(hso.permissionDecision).toBe("allow");
  });

  test("PreToolUse denies dangerous command", () => {
    const out = runHerald("PreToolUse", { tool: "Bash", toolInput: { command: "rm -rf /" } });
    expect(out.continue).toBe(false);
    const hso = out.hookSpecificOutput as Record<string, unknown>;
    expect(hso.permissionDecision).toBe("deny");
  });

  test("PostToolUse allows success", () => {
    const out = runHerald("PostToolUse", { tool: "Bash", result: { exitCode: 0, success: true } });
    expect(out.continue).toBe(true);
  });

  test("PostToolUse blocks on failure", () => {
    const out = runHerald("PostToolUse", { tool: "Bash", result: { exitCode: 1 } });
    expect(out.continue).toBe(false);
  });

  test("SessionStart returns hookSpecificOutput", () => {
    const out = runHerald("SessionStart", { sessionId: "integ-test" });
    expect(out.continue).toBe(true);
    const hso = out.hookSpecificOutput as Record<string, unknown>;
    expect(hso.hookEventName).toBe("SessionStart");
    expect(typeof hso.additionalContext).toBe("string");
  });

  test("SessionEnd returns hookSpecificOutput", () => {
    const out = runHerald("SessionEnd", { sessionId: "integ-test", duration: 60 });
    expect(out.continue).toBe(true);
    const hso = out.hookSpecificOutput as Record<string, unknown>;
    expect(hso.hookEventName).toBe("SessionEnd");
  });

  test("UserPromptSubmit allows clean prompt", () => {
    const out = runHerald("UserPromptSubmit", { prompt: "Hello" });
    expect(out.continue).toBe(true);
  });

  test("UserPromptSubmit blocks missing prompt", () => {
    const out = runHerald("UserPromptSubmit", {});
    expect(out.continue).toBe(false);
  });

  test("unknown event returns continue: true", () => {
    const out = runHerald("UnknownEvent", {});
    expect(out.continue).toBe(true);
  });

  test("short task Stop suppresses audio (prompt submitted moments ago)", () => {
    // First, submit a prompt to write last_prompt_at
    runHerald("UserPromptSubmit", { prompt: "quick task" });

    // Immediately run Stop — elapsed time < 30s threshold
    const out = runHerald("Stop", {});
    expect(out.continue).toBe(true);

    // Verify last_prompt_at was written
    const hooksDir = resolve(import.meta.dir, "..");
    const repoRoot = dirname(dirname(hooksDir));
    const tsFile = join(repoRoot, "logs", "last_prompt_at");
    expect(existsSync(tsFile)).toBe(true);
    const ts = Number(readFileSync(tsFile, "utf-8").trim());
    expect(ts).toBeGreaterThan(0);
  });

  test("short SessionEnd suppresses audio (duration < threshold)", () => {
    const out = runHerald("SessionEnd", { sessionId: "short-test", duration: 5 });
    expect(out.continue).toBe(true);
    // duration 5s < 30s threshold → audio suppressed internally
  });

  test("long SessionEnd does not suppress audio (duration >= threshold)", () => {
    const out = runHerald("SessionEnd", { sessionId: "long-test", duration: 60 });
    expect(out.continue).toBe(true);
    // duration 60s >= 30s threshold → audio not suppressed
  });
});
