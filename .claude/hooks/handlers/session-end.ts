/**
 * SessionEnd handler — cleanup + state update.
 */

import { existsSync, rmSync, statSync } from "fs";
import { join, resolve, dirname } from "path";
import type { HookContext, HandlerResult } from "../lib/types";
import { createResult } from "../lib/types";
import { SESSION_END } from "../lib/constants";
import { loadState, writeState, appendEventLog, getRepoRoot } from "../lib/session";

const REPO_ROOT = getRepoRoot();

function utcTimestamp(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

function parseDuration(value: unknown): number | null {
  if (typeof value === "number") return value;
  if (typeof value === "string") {
    const n = Number(value);
    return isNaN(n) ? null : n;
  }
  return null;
}

function sessionRootPath(sessionId: string): string {
  return join(REPO_ROOT, "logs", "sessions", sessionId);
}

function cleanupResources(
  sessionId: string,
  resources: unknown[],
): { removed: string[]; skipped: string[] } {
  const removed: string[] = [];
  const skipped: string[] = [];
  const base = sessionRootPath(sessionId);

  for (const item of resources) {
    if (typeof item !== "string") continue;
    let candidate: string;
    if (item.startsWith("/")) {
      candidate = resolve(item);
    } else {
      candidate = resolve(base, item);
    }

    try {
      // Security: only allow cleanup within session directory
      if (!candidate.startsWith(base)) {
        skipped.push(String(candidate));
        continue;
      }

      if (existsSync(candidate)) {
        const stat = statSync(candidate);
        if (stat.isDirectory()) {
          rmSync(candidate, { recursive: true, force: true });
        } else {
          rmSync(candidate, { force: true });
        }
        removed.push(candidate);
      }
    } catch {
      skipped.push(String(candidate));
    }
  }

  return { removed, skipped };
}

function finaliseSession(payload: Record<string, unknown>): string {
  const sessionId = String(payload.session_id ?? payload.sessionId ?? "unknown-session");
  const endTime = typeof payload.end_time === "string" ? payload.end_time : utcTimestamp();
  const duration = parseDuration(payload.duration);
  const terminationReason = String(payload.termination_reason ?? payload.reason ?? "normal");
  const statistics =
    typeof payload.statistics === "object" && payload.statistics !== null
      ? (payload.statistics as Record<string, unknown>)
      : {};
  let resources = payload.resources_to_cleanup ?? payload.cleanup ?? [];
  if (!Array.isArray(resources)) resources = [];

  const { removed, skipped } = cleanupResources(sessionId, resources as unknown[]);

  const state = loadState() as Record<string, Record<string, unknown>>;
  const entry = (state[sessionId] ?? {}) as Record<string, unknown>;
  const entryState = (typeof entry.state === "object" && entry.state !== null
    ? entry.state
    : {}) as Record<string, unknown>;
  entryState.status = "ended";
  entryState.endedAt = endTime;
  entryState.termination = terminationReason;
  if (duration !== null) entryState.durationSeconds = duration;
  entry.state = entryState;

  const history = Array.isArray(entry.history) ? entry.history : [];
  history.push({
    event: "session_end",
    timestamp: endTime,
    termination: terminationReason,
    removed,
    skipped,
  });
  entry.history = history;
  entry.statistics = statistics;
  state[sessionId] = entry;
  writeState(state);

  appendEventLog({
    sessionId,
    event: "session_end",
    timestamp: endTime,
    termination: terminationReason,
    removed,
    skipped,
  });

  return JSON.stringify({
    sessionId,
    endedAt: endTime,
    termination: terminationReason,
    durationSeconds: duration,
    statistics,
    removedResources: removed,
    skippedResources: skipped,
  });
}

export function handleSessionEnd(context: HookContext): HandlerResult {
  const hr = createResult({ audioType: SESSION_END });
  try {
    const payload = typeof context.payload === "object" && context.payload !== null ? context.payload : {};
    const summaryJson = finaliseSession(payload);
    hr.response.hookSpecificOutput = {
      hookEventName: SESSION_END,
      additionalContext: summaryJson,
    };
  } catch {
    // silent
  }
  return hr;
}
