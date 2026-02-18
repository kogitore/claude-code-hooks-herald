/**
 * SessionStart handler — session initialization + health checks.
 */

import { existsSync, mkdirSync } from "fs";
import { join, dirname, resolve } from "path";
import type { HookContext, HandlerResult } from "../lib/types";
import { createResult } from "../lib/types";
import { SESSION_START } from "../lib/constants";
import { loadState, writeState, appendEventLog, getRepoRoot } from "../lib/session";

const REPO_ROOT = getRepoRoot();

function utcTimestamp(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

function sessionRootPath(sessionId: string): string {
  const envRoot = process.env.CLAUDE_SESSION_ROOT;
  let base: string;
  if (envRoot) {
    base = envRoot.startsWith("/") ? envRoot : join(REPO_ROOT, envRoot);
  } else {
    base = join(REPO_ROOT, "logs", "sessions");
  }
  return join(base, sessionId);
}

function ensureDir(path: string): void {
  try {
    if (!existsSync(path)) mkdirSync(path, { recursive: true });
  } catch {
    // silent
  }
}

function runHealthChecks(
  environment: Record<string, unknown>,
  preferences: Record<string, unknown>,
): { checks: string[]; warnings: string[] } {
  const checks: string[] = [];
  const warnings: string[] = [];

  const workingDir = environment.working_directory;
  if (typeof workingDir === "string") {
    if (existsSync(workingDir)) {
      checks.push("working_directory_exists");
    } else {
      warnings.push("working_directory_missing");
    }
  }

  const soundsDir = join(REPO_ROOT, ".claude", "sounds");
  if (existsSync(soundsDir)) {
    checks.push("sounds_directory_present");
  } else {
    warnings.push("sounds_directory_missing");
  }

  if (preferences.audio_enabled === false) {
    warnings.push("audio_disabled_by_user");
  }

  return { checks, warnings };
}

function initialiseSession(payload: Record<string, unknown>): string {
  const sessionId = String(payload.session_id ?? payload.sessionId ?? "unknown-session");
  const userId = (payload.user_id ?? payload.userId ?? null) as string | null;
  const startTime = typeof payload.start_time === "string" ? payload.start_time : utcTimestamp();
  const environment = (typeof payload.environment === "object" && payload.environment !== null
    ? payload.environment
    : {}) as Record<string, unknown>;
  const preferences = (typeof payload.preferences === "object" && payload.preferences !== null
    ? payload.preferences
    : {}) as Record<string, unknown>;

  const sessionRoot = sessionRootPath(sessionId);
  ensureDir(sessionRoot);

  const { checks, warnings } = runHealthChecks(environment, preferences);

  const state = loadState() as Record<string, Record<string, unknown>>;
  state[sessionId] = {
    sessionId,
    userId,
    startedAt: startTime,
    environment,
    preferences,
    state: { status: "active" },
    history: [
      {
        event: "session_start",
        timestamp: startTime,
        checks,
        warnings,
      },
    ],
  };
  writeState(state);
  appendEventLog({
    sessionId,
    event: "session_start",
    timestamp: startTime,
    checks,
    warnings,
  });

  const summary: Record<string, unknown> = {
    sessionId,
    userId,
    startedAt: startTime,
    setupChecks: checks,
    warnings,
    workspace: sessionRoot,
  };
  if (Object.keys(preferences).length > 0) summary.preferences = preferences;
  if (Object.keys(environment).length > 0) summary.environment = environment;

  return JSON.stringify(summary);
}

export function handleSessionStart(context: HookContext): HandlerResult {
  const hr = createResult({ audioType: SESSION_START });
  try {
    const payload = typeof context.payload === "object" && context.payload !== null ? context.payload : {};
    const summaryJson = initialiseSession(payload);
    hr.response.hookSpecificOutput = {
      hookEventName: SESSION_START,
      additionalContext: summaryJson,
    };
  } catch {
    // Silent failure: never block session
  }
  return hr;
}
