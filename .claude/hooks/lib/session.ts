/**
 * Minimal session storage — file-based state and event logging.
 * Port of session_storage.py.
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync, appendFileSync } from "fs";
import { dirname, join, resolve } from "path";

const HOOKS_DIR = dirname(dirname(resolve(import.meta.dir)));
const REPO_ROOT = dirname(HOOKS_DIR);

const LOGS_ROOT = join(REPO_ROOT, "logs");
const STATE_PATH = join(LOGS_ROOT, "session_state.json");
const EVENT_LOG_PATH = join(LOGS_ROOT, "session_events.jsonl");

function ensureDir(dir: string): void {
  try {
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  } catch {
    // silent
  }
}

export function loadState(): Record<string, unknown> {
  try {
    ensureDir(LOGS_ROOT);
    if (existsSync(STATE_PATH)) {
      return JSON.parse(readFileSync(STATE_PATH, "utf-8"));
    }
  } catch {
    // silent
  }
  return {};
}

export function writeState(state: Record<string, unknown>): void {
  try {
    ensureDir(LOGS_ROOT);
    writeFileSync(STATE_PATH, JSON.stringify(state, null, 2));
  } catch {
    // silent
  }
}

export function appendEventLog(event: Record<string, unknown>): void {
  try {
    ensureDir(LOGS_ROOT);
    appendFileSync(EVENT_LOG_PATH, JSON.stringify(event) + "\n");
  } catch {
    // silent
  }
}

export function getLogsRoot(): string {
  return LOGS_ROOT;
}

export function getRepoRoot(): string {
  return REPO_ROOT;
}
