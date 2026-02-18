#!/usr/bin/env bun
/**
 * Deep configuration validator — checks audio mappings, decision policy,
 * i18n messages, and settings.json hook routing for consistency.
 *
 * Usage:
 *   bun run scripts/validate-config.ts          # human-readable
 *   bun run scripts/validate-config.ts --json   # machine-readable JSON
 *   bun run validate
 */

import { existsSync, readFileSync } from "fs";
import { join, resolve, dirname } from "path";

// ── Paths ──────────────────────────────────────────────────────────────────────
const SCRIPTS_DIR = dirname(resolve(import.meta.filename));
const REPO_ROOT = dirname(SCRIPTS_DIR);
const HOOKS_DIR = join(REPO_ROOT, ".claude", "hooks");
const CONFIG_DIR = join(HOOKS_DIR, "config");
const SOUNDS_DIR = join(REPO_ROOT, ".claude", "sounds");
const SETTINGS_PATH = join(REPO_ROOT, ".claude", "settings.json");

// Import constants inline (avoid TS path issues in standalone script)
const ALL_EVENTS = [
  "Notification", "Stop", "SubagentStop", "PreToolUse",
  "PostToolUse", "UserPromptSubmit", "SessionStart", "SessionEnd", "PreCompact",
] as const;

// Events that should have hook routing in settings.json (PreCompact has no handler)
const ROUTED_EVENTS = ALL_EVENTS.filter((e) => e !== "PreCompact");

// Events that should have notification messages
const NOTIFY_EVENTS = ["Stop", "SubagentStop", "Notification", "SessionEnd"];

// ── Colors ─────────────────────────────────────────────────────────────────────
const green = (s: string) => `\x1b[32m${s}\x1b[0m`;
const red = (s: string) => `\x1b[31m${s}\x1b[0m`;
const yellow = (s: string) => `\x1b[33m${s}\x1b[0m`;
const blue = (s: string) => `\x1b[34m${s}\x1b[0m`;
const dim = (s: string) => `\x1b[2m${s}\x1b[0m`;

// ── JSON output mode ───────────────────────────────────────────────────────────
const jsonMode = process.argv.includes("--json");

interface Issue {
  section: string;
  level: "error" | "warn";
  message: string;
}

const issues: Issue[] = [];

function pass(section: string, msg: string) {
  if (!jsonMode) console.log(`  ${green("PASS")}  ${msg}`);
}

function fail(section: string, msg: string) {
  issues.push({ section, level: "error", message: msg });
  if (!jsonMode) console.log(`  ${red("FAIL")}  ${msg}`);
}

function warn(section: string, msg: string) {
  issues.push({ section, level: "warn", message: msg });
  if (!jsonMode) console.log(`  ${yellow("WARN")}  ${msg}`);
}

function sectionHeader(title: string) {
  if (!jsonMode) {
    console.log(`\n${blue(title)}`);
    console.log(blue("─".repeat(title.length)));
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function loadJson(path: string): unknown | null {
  try {
    return JSON.parse(readFileSync(path, "utf-8"));
  } catch {
    return null;
  }
}

// ── Validators ─────────────────────────────────────────────────────────────────

function validateAudioConfig() {
  const S = "audio.json";
  sectionHeader("audio.json");

  const path = join(CONFIG_DIR, "audio.json");
  if (!existsSync(path)) {
    fail(S, "audio.json not found");
    return;
  }

  const data = loadJson(path) as Record<string, unknown> | null;
  if (!data) {
    fail(S, "audio.json — invalid JSON");
    return;
  }

  pass(S, "Valid JSON");

  // Check mappings
  const sf = data.sound_files as Record<string, unknown> | undefined;
  const mappings = (sf?.mappings ?? {}) as Record<string, unknown>;
  const mappedEvents = Object.keys(mappings);

  // Events in mappings that aren't in constants
  for (const key of mappedEvents) {
    if (!ALL_EVENTS.includes(key as any)) {
      warn(S, `Unknown event in mappings: "${key}"`);
    }
  }

  // Events in constants that aren't in mappings (excluding PreCompact)
  for (const event of ROUTED_EVENTS) {
    if (!(event in mappings)) {
      warn(S, `Event "${event}" has no audio mapping`);
    }
  }

  // Sound files exist?
  const basePath = (sf?.base_path as string) ?? "./.claude/sounds";
  const resolvedBase = basePath.startsWith("/") ? basePath : join(REPO_ROOT, basePath);

  for (const [event, files] of Object.entries(mappings)) {
    const fileList = Array.isArray(files) ? files : [files];
    for (const f of fileList) {
      const fullPath = join(resolvedBase, f as string);
      if (!existsSync(fullPath)) {
        warn(S, `Sound file missing: ${f} (event: ${event})`);
      } else {
        pass(S, `${event} → ${f}`);
      }
    }
  }

  // Throttle values
  const as = data.audio_settings as Record<string, unknown> | undefined;
  const throttle = (as?.throttle_seconds ?? {}) as Record<string, unknown>;

  for (const [key, val] of Object.entries(throttle)) {
    const n = Number(val);
    if (isNaN(n) || n < 0) {
      fail(S, `Invalid throttle for "${key}": ${val}`);
    } else if (n > 600) {
      warn(S, `Throttle for "${key}" is very high: ${n}s`);
    }
  }

  // Volume
  const volume = Number(as?.volume ?? 0.2);
  if (volume < 0 || volume > 1) {
    fail(S, `Volume out of range [0,1]: ${volume}`);
  }

  // min_task_duration_seconds
  const minDuration = Number(as?.min_task_duration_seconds ?? 0);
  if (minDuration < 0) {
    fail(S, `min_task_duration_seconds is negative: ${minDuration}`);
  }
}

function validateDecisionPolicy() {
  const S = "decision-policy.json";
  sectionHeader("decision-policy.json");

  const path = join(CONFIG_DIR, "decision-policy.json");
  if (!existsSync(path)) {
    warn(S, "decision-policy.json not found (optional)");
    return;
  }

  const data = loadJson(path) as Record<string, unknown> | null;
  if (!data) {
    fail(S, "decision-policy.json — invalid JSON");
    return;
  }

  pass(S, "Valid JSON");

  const validActions = new Set(["allow", "deny", "ask"]);

  // Check pre_tool_use rules
  const preToolUse = data.pre_tool_use as Record<string, unknown> | undefined;
  const rules = (preToolUse?.rules ?? []) as Record<string, unknown>[];

  for (let i = 0; i < rules.length; i++) {
    const rule = rules[i];

    // Validate action
    if (rule.action && !validActions.has(rule.action as string)) {
      fail(S, `Rule #${i + 1}: invalid action "${rule.action}" (expected: allow/deny/ask)`);
    }

    // Validate regex pattern compiles
    if (typeof rule.pattern === "string") {
      try {
        new RegExp(rule.pattern);
        pass(S, `Rule #${i + 1}: pattern compiles — "${rule.pattern}"`);
      } catch (e) {
        fail(S, `Rule #${i + 1}: invalid regex "${rule.pattern}" — ${e instanceof Error ? e.message : e}`);
      }
    }

    // Validate severity
    const validSeverity = ["critical", "high", "medium", "low"];
    if (rule.severity && !validSeverity.includes(rule.severity as string)) {
      warn(S, `Rule #${i + 1}: unusual severity "${rule.severity}"`);
    }
  }

  if (rules.length > 0) {
    pass(S, `${rules.length} pre_tool_use rule(s) validated`);
  }
}

function validateMessages() {
  const S = "messages.json";
  sectionHeader("messages.json");

  const path = join(CONFIG_DIR, "messages.json");
  if (!existsSync(path)) {
    warn(S, "messages.json not found (will use default English messages)");
    return;
  }

  const data = loadJson(path) as Record<string, unknown> | null;
  if (!data) {
    fail(S, "messages.json — invalid JSON");
    return;
  }

  pass(S, "Valid JSON");

  const messages = (data.messages ?? {}) as Record<string, unknown>;

  // Check notification events have messages
  for (const event of NOTIFY_EVENTS) {
    if (typeof messages[event] === "string") {
      pass(S, `${event}: "${messages[event]}"`);
    } else {
      warn(S, `No i18n message for notify event: ${event}`);
    }
  }

  // Check for unknown events in messages
  for (const key of Object.keys(messages)) {
    if (!ALL_EVENTS.includes(key as any)) {
      warn(S, `Message for unknown event: "${key}"`);
    }
  }
}

function validateSettings() {
  const S = "settings.json";
  sectionHeader("settings.json");

  if (!existsSync(SETTINGS_PATH)) {
    fail(S, "settings.json not found");
    return;
  }

  const data = loadJson(SETTINGS_PATH) as Record<string, unknown> | null;
  if (!data) {
    fail(S, "settings.json — invalid JSON");
    return;
  }

  pass(S, "Valid JSON");

  const hooks = data.hooks as Record<string, unknown> | undefined;
  if (!hooks || typeof hooks !== "object") {
    fail(S, "No hooks section");
    return;
  }

  let routed = 0;
  for (const event of ROUTED_EVENTS) {
    const entries = hooks[event] as unknown[] | undefined;
    if (!entries || !Array.isArray(entries)) {
      fail(S, `Event "${event}" — not configured`);
      continue;
    }

    // Extract commands
    let heraldCmd: string | null = null;
    for (const entry of entries) {
      const e = entry as Record<string, unknown>;
      const hookList = e.hooks as unknown[] | undefined;
      if (!hookList) continue;
      for (const h of hookList) {
        const hk = h as Record<string, unknown>;
        if (typeof hk.command === "string" && hk.command.includes("herald.ts")) {
          heraldCmd = hk.command;
        }
      }
    }

    if (heraldCmd) {
      // Verify command includes --hook EventName
      if (heraldCmd.includes(`--hook ${event}`)) {
        pass(S, `${event} → ${dim(heraldCmd)}`);
        routed++;
      } else {
        warn(S, `${event} — command doesn't include "--hook ${event}": ${heraldCmd}`);
      }
    } else {
      fail(S, `${event} — not routed to herald.ts`);
    }
  }

  // Check for unknown events in hooks
  for (const key of Object.keys(hooks)) {
    if (!ALL_EVENTS.includes(key as any)) {
      warn(S, `Unknown event configured: "${key}"`);
    }
  }

  if (!jsonMode) {
    console.log(`\n  ${dim(`${routed}/${ROUTED_EVENTS.length} events correctly routed`)}`);
  }
}

// ── Main ───────────────────────────────────────────────────────────────────────

if (!jsonMode) {
  console.log(blue("Herald Configuration Validator"));
  console.log(blue("=============================="));
}

validateAudioConfig();
validateDecisionPolicy();
validateMessages();
validateSettings();

// ── Output ─────────────────────────────────────────────────────────────────────

const errorCount = issues.filter((i) => i.level === "error").length;
const warnCount = issues.filter((i) => i.level === "warn").length;

if (jsonMode) {
  const report = {
    valid: errorCount === 0,
    errors: errorCount,
    warnings: warnCount,
    issues,
  };
  console.log(JSON.stringify(report, null, 2));
} else {
  console.log("");
  console.log(blue("Summary"));
  console.log(blue("───────"));

  if (errorCount === 0 && warnCount === 0) {
    console.log(green("All validations passed."));
  } else if (errorCount === 0) {
    console.log(yellow(`Valid with ${warnCount} warning(s).`));
  } else {
    console.log(red(`${errorCount} error(s), ${warnCount} warning(s).`));
  }
}

process.exit(errorCount > 0 ? 1 : 0);
