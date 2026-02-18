#!/usr/bin/env bun
/**
 * Health check — validates Bun environment, audio players, configs, and hook routing.
 *
 * Usage:
 *   bun run scripts/health-check.ts
 *   bun run health
 */

import { existsSync, mkdirSync, writeFileSync, unlinkSync, readFileSync } from "fs";
import { join, resolve, dirname } from "path";

// ── Paths ──────────────────────────────────────────────────────────────────────
const SCRIPTS_DIR = dirname(resolve(import.meta.filename));
const REPO_ROOT = dirname(SCRIPTS_DIR);
const HOOKS_DIR = join(REPO_ROOT, ".claude", "hooks");
const CONFIG_DIR = join(HOOKS_DIR, "config");
const SOUNDS_DIR = join(REPO_ROOT, ".claude", "sounds");
const LOGS_DIR = join(REPO_ROOT, "logs");
const SETTINGS_PATH = join(REPO_ROOT, ".claude", "settings.json");

// ── Colors ─────────────────────────────────────────────────────────────────────
const green = (s: string) => `\x1b[32m${s}\x1b[0m`;
const red = (s: string) => `\x1b[31m${s}\x1b[0m`;
const yellow = (s: string) => `\x1b[33m${s}\x1b[0m`;
const blue = (s: string) => `\x1b[34m${s}\x1b[0m`;
const dim = (s: string) => `\x1b[2m${s}\x1b[0m`;

// ── State ──────────────────────────────────────────────────────────────────────
let errors = 0;
let warnings = 0;

function pass(msg: string) {
  console.log(`  ${green("PASS")}  ${msg}`);
}

function fail(msg: string) {
  errors++;
  console.log(`  ${red("FAIL")}  ${msg}`);
}

function warn(msg: string) {
  warnings++;
  console.log(`  ${yellow("WARN")}  ${msg}`);
}

function info(msg: string) {
  console.log(`  ${dim("INFO")}  ${msg}`);
}

function section(title: string) {
  console.log(`\n${blue(title)}`);
  console.log(blue("─".repeat(title.length)));
}

// ── Checks ─────────────────────────────────────────────────────────────────────

function checkBunRuntime() {
  section("Bun Runtime");
  const version = Bun.version;
  if (version) {
    pass(`Bun ${version} (${process.platform}/${process.arch})`);
  } else {
    fail("Could not detect Bun version");
  }
}

function checkAudioPlayers() {
  section("Audio Player Detection");

  const players: string[] = [];

  if (process.platform === "darwin" && Bun.which("afplay")) {
    players.push("afplay");
    pass("afplay (macOS native)");
  }

  if (Bun.which("ffplay")) {
    players.push("ffplay");
    pass("ffplay (FFmpeg)");
  }

  if (Bun.which("aplay")) {
    players.push("aplay");
    pass("aplay (ALSA)");
  }

  if (process.platform === "win32" && Bun.which("powershell")) {
    players.push("powershell");
    pass("powershell (Windows)");
  }

  if (players.length === 0) {
    fail("No audio player detected");
  }

  if (process.env.AUDIO_PLAYER_CMD) {
    info(`AUDIO_PLAYER_CMD override: ${process.env.AUDIO_PLAYER_CMD}`);
  }
}

function checkSoundFiles() {
  section("Sound Files");

  if (!existsSync(SOUNDS_DIR)) {
    warn(`Sounds directory not found: ${SOUNDS_DIR}`);
    return;
  }

  pass(`Sounds directory exists`);

  // Check for actual .wav files (not .example)
  const glob = new Bun.Glob("*.wav");
  const wavFiles = [...glob.scanSync(SOUNDS_DIR)];

  if (wavFiles.length === 0) {
    warn("No .wav files found (copy .wav.example files and rename)");
  } else {
    pass(`${wavFiles.length} sound file(s): ${wavFiles.join(", ")}`);
  }

  // Check .example files
  const exampleGlob = new Bun.Glob("*.wav.example");
  const examples = [...exampleGlob.scanSync(SOUNDS_DIR)];
  if (examples.length > 0) {
    info(`${examples.length} example file(s) available`);
  }
}

function checkConfigFiles() {
  section("Configuration Files");

  const configs = [
    { name: "audio.json", path: join(CONFIG_DIR, "audio.json"), required: true },
    { name: "decision-policy.json", path: join(CONFIG_DIR, "decision-policy.json"), required: true },
    { name: "messages.json", path: join(CONFIG_DIR, "messages.json"), required: false },
  ];

  for (const cfg of configs) {
    if (!existsSync(cfg.path)) {
      if (cfg.required) {
        fail(`${cfg.name} not found`);
      } else {
        warn(`${cfg.name} not found (optional)`);
      }
      continue;
    }

    try {
      JSON.parse(readFileSync(cfg.path, "utf-8"));
      pass(`${cfg.name} — valid JSON`);
    } catch (e) {
      fail(`${cfg.name} — invalid JSON: ${e instanceof Error ? e.message : e}`);
    }
  }
}

function checkSettingsRouting() {
  section("Hook Routing (settings.json)");

  if (!existsSync(SETTINGS_PATH)) {
    fail("settings.json not found");
    return;
  }

  let settings: Record<string, unknown>;
  try {
    settings = JSON.parse(readFileSync(SETTINGS_PATH, "utf-8"));
  } catch {
    fail("settings.json — invalid JSON");
    return;
  }

  const hooks = settings.hooks as Record<string, unknown> | undefined;
  if (!hooks || typeof hooks !== "object") {
    fail("No hooks section in settings.json");
    return;
  }

  const expectedEvents = [
    "Notification", "Stop", "SubagentStop", "PreToolUse",
    "PostToolUse", "SessionStart", "SessionEnd", "UserPromptSubmit",
  ];

  let routed = 0;
  for (const event of expectedEvents) {
    const entries = hooks[event] as unknown[] | undefined;
    if (!entries || !Array.isArray(entries)) {
      warn(`${event} — not configured`);
      continue;
    }

    // Check if any hook command points to herald.ts
    let found = false;
    for (const entry of entries) {
      const e = entry as Record<string, unknown>;
      const hookList = e.hooks as unknown[] | undefined;
      if (!hookList) continue;
      for (const h of hookList) {
        const hk = h as Record<string, unknown>;
        if (typeof hk.command === "string" && hk.command.includes("herald.ts")) {
          found = true;
        }
      }
    }

    if (found) {
      pass(`${event} → herald.ts`);
      routed++;
    } else {
      warn(`${event} — not routed to herald.ts`);
    }
  }

  info(`${routed}/${expectedEvents.length} events routed`);
}

function checkLogsDirectory() {
  section("Logs Directory");

  if (!existsSync(LOGS_DIR)) {
    try {
      mkdirSync(LOGS_DIR, { recursive: true });
      pass("logs/ created");
    } catch {
      fail("Cannot create logs/ directory");
      return;
    }
  }

  // Test writability
  const testFile = join(LOGS_DIR, ".health-check-probe");
  try {
    writeFileSync(testFile, "ok");
    unlinkSync(testFile);
    pass("logs/ is writable");
  } catch {
    fail("logs/ is not writable");
  }
}

// ── Main ───────────────────────────────────────────────────────────────────────

console.log(blue("Herald Health Check"));
console.log(blue("==================="));

checkBunRuntime();
checkAudioPlayers();
checkSoundFiles();
checkConfigFiles();
checkSettingsRouting();
checkLogsDirectory();

// Summary
console.log("");
console.log(blue("Summary"));
console.log(blue("───────"));

if (errors === 0 && warnings === 0) {
  console.log(green("All checks passed."));
} else if (errors === 0) {
  console.log(yellow(`Passed with ${warnings} warning(s).`));
} else {
  console.log(red(`${errors} error(s), ${warnings} warning(s).`));
}

process.exit(errors > 0 ? 1 : 0);
