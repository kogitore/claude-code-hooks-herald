#!/usr/bin/env bun
/**
 * Interactive event tester — fire hook events and inspect herald responses.
 *
 * Usage:
 *   bun run scripts/test-event.ts Stop
 *   bun run scripts/test-event.ts PreToolUse '{"tool":"Bash","toolInput":{"command":"ls"}}'
 *   bun run scripts/test-event.ts --all
 *   bun run scripts/test-event.ts --sound Stop    # play audio
 *   bun run test:event Stop
 */

import { resolve, dirname, join } from "path";

// ── Paths ──────────────────────────────────────────────────────────────────────
const SCRIPTS_DIR = dirname(resolve(import.meta.filename));
const REPO_ROOT = dirname(SCRIPTS_DIR);
const HERALD_PATH = join(REPO_ROOT, ".claude", "hooks", "herald.ts");

// ── Colors ─────────────────────────────────────────────────────────────────────
const green = (s: string) => `\x1b[32m${s}\x1b[0m`;
const red = (s: string) => `\x1b[31m${s}\x1b[0m`;
const yellow = (s: string) => `\x1b[33m${s}\x1b[0m`;
const blue = (s: string) => `\x1b[34m${s}\x1b[0m`;
const cyan = (s: string) => `\x1b[36m${s}\x1b[0m`;
const dim = (s: string) => `\x1b[2m${s}\x1b[0m`;

// ── Default Payloads ───────────────────────────────────────────────────────────
const DEFAULT_PAYLOADS: Record<string, Record<string, unknown>> = {
  Notification: {
    message: "Test notification from herald",
  },
  Stop: {
    stopReason: "end_turn",
  },
  SubagentStop: {
    stopReason: "end_turn",
    agentName: "test-subagent",
  },
  PreToolUse: {
    tool: "Bash",
    toolInput: { command: "echo hello" },
  },
  PostToolUse: {
    tool: "Bash",
    toolInput: { command: "echo hello" },
    toolResult: { stdout: "hello\n", exitCode: 0 },
  },
  UserPromptSubmit: {
    prompt: "Test prompt from event tester",
    user_id: "tester",
    session_id: "test-session-001",
  },
  SessionStart: {
    session_id: "test-session-001",
    startedAt: new Date().toISOString(),
  },
  SessionEnd: {
    session_id: "test-session-001",
    duration: 120,
    termination_reason: "normal",
  },
};

const ALL_EVENTS = Object.keys(DEFAULT_PAYLOADS);

// ── Helpers ────────────────────────────────────────────────────────────────────

function formatJson(obj: unknown): string {
  const raw = JSON.stringify(obj, null, 2);
  // Simple syntax highlighting
  return raw
    .replace(/"([^"]+)":/g, `${cyan('"$1"')}:`)
    .replace(/: "([^"]*)"/g, `: ${green('"$1"')}`)
    .replace(/: (true|false)/g, `: ${yellow("$1")}`)
    .replace(/: (\d+(?:\.\d+)?)/g, `: ${yellow("$1")}`);
}

interface TestResult {
  event: string;
  success: boolean;
  response: Record<string, unknown> | null;
  error: string | null;
  durationMs: number;
}

async function fireEvent(
  event: string,
  payload: Record<string, unknown>,
  silent: boolean,
): Promise<TestResult> {
  const start = performance.now();
  const input = JSON.stringify(payload);

  const env: Record<string, string> = { ...process.env as Record<string, string> };
  if (silent) {
    env.AUDIO_PLAYER_CMD = "true";
  }

  try {
    const proc = Bun.spawn(["bun", "run", HERALD_PATH, "--hook", event], {
      stdin: new Blob([input]),
      stdout: "pipe",
      stderr: "pipe",
      env,
      cwd: REPO_ROOT,
    });

    const stdout = await new Response(proc.stdout).text();
    await proc.exited;
    const durationMs = Math.round(performance.now() - start);

    const line = stdout.trim().split("\n")[0] ?? "";
    if (!line) {
      return { event, success: false, response: null, error: "Empty response", durationMs };
    }

    try {
      const response = JSON.parse(line);
      return { event, success: true, response, error: null, durationMs };
    } catch {
      return { event, success: false, response: null, error: `Invalid JSON: ${line.slice(0, 200)}`, durationMs };
    }
  } catch (e) {
    const durationMs = Math.round(performance.now() - start);
    return {
      event,
      success: false,
      response: null,
      error: e instanceof Error ? e.message : String(e),
      durationMs,
    };
  }
}

// ── CLI Parsing ────────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
const flags = new Set(args.filter((a) => a.startsWith("--")));
const positional = args.filter((a) => !a.startsWith("--"));

const runAll = flags.has("--all");
const playSound = flags.has("--sound");
const silent = !playSound; // Default: silent

if (!runAll && positional.length === 0) {
  console.log(blue("Herald Event Tester"));
  console.log(blue("===================\n"));
  console.log("Usage:");
  console.log(`  bun run test:event <Event>                    Test single event`);
  console.log(`  bun run test:event <Event> '<json>'           Test with custom payload`);
  console.log(`  bun run test:event -- --all                   Test all events`);
  console.log(`  bun run test:event -- --sound <Event>         Test with audio\n`);
  console.log("Events:");
  for (const event of ALL_EVENTS) {
    console.log(`  ${event}`);
  }
  process.exit(0);
}

// ── Run ────────────────────────────────────────────────────────────────────────

const events = runAll ? ALL_EVENTS : [positional[0]];

// Parse custom payload if provided
let customPayload: Record<string, unknown> | null = null;
if (!runAll && positional[1]) {
  try {
    customPayload = JSON.parse(positional[1]);
  } catch {
    console.error(red(`Invalid JSON payload: ${positional[1]}`));
    process.exit(1);
  }
}

// Validate event name
if (!runAll) {
  const event = positional[0];
  if (!ALL_EVENTS.includes(event)) {
    console.error(red(`Unknown event: "${event}"`));
    console.error(`Available: ${ALL_EVENTS.join(", ")}`);
    process.exit(1);
  }
}

console.log(blue("Herald Event Tester"));
console.log(blue("==================="));
console.log(dim(`Mode: ${silent ? "silent" : "with sound"}\n`));

const results: TestResult[] = [];

for (const event of events) {
  const payload = customPayload ?? DEFAULT_PAYLOADS[event] ?? {};

  console.log(`${blue("Event:")} ${event}`);
  console.log(`${dim("Payload:")} ${dim(JSON.stringify(payload))}`);

  const result = await fireEvent(event, payload, silent);
  results.push(result);

  if (result.success) {
    console.log(`${green("PASS")} ${dim(`(${result.durationMs}ms)`)}`);
    console.log(formatJson(result.response));
  } else {
    console.log(`${red("FAIL")} ${result.error}`);
  }

  console.log("");
}

// ── Summary ────────────────────────────────────────────────────────────────────

if (results.length > 1) {
  console.log(blue("Summary"));
  console.log(blue("───────"));

  const passed = results.filter((r) => r.success).length;
  const failed = results.filter((r) => !r.success).length;
  const totalMs = results.reduce((s, r) => s + r.durationMs, 0);

  for (const r of results) {
    const icon = r.success ? green("PASS") : red("FAIL");
    console.log(`  ${icon}  ${r.event} ${dim(`(${r.durationMs}ms)`)}`);
  }

  console.log("");
  console.log(`${passed}/${results.length} passed ${dim(`(${totalMs}ms total)`)}`);

  if (failed > 0) {
    process.exit(1);
  }
}

process.exit(results.some((r) => !r.success) ? 1 : 0);
