/**
 * UserPromptSubmit handler — prompt validation + rate limiting.
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync, appendFileSync } from "fs";
import { join, dirname } from "path";
import type { HookContext, HandlerResult } from "../lib/types";
import { createResult } from "../lib/types";
import { USER_PROMPT_SUBMIT } from "../lib/constants";
import { getRepoRoot } from "../lib/session";

const REPO_ROOT = getRepoRoot();
const PROMPT_LOG_PATH = join(REPO_ROOT, "logs", "prompt_submissions.jsonl");
const RATE_LIMIT_PATH = join(REPO_ROOT, "logs", "prompt_rates.json");
const MAX_PROMPT_LENGTH = 4000;
const MAX_PREVIEW = 240;
const RATE_LIMIT_SECONDS = 1.0;

const SUSPICIOUS_PATTERNS: [RegExp, string][] = [
  [/rm\s+-rf\s+/i, "dangerous_command"],
  [/drop\s+table/i, "sql_drop"],
  [/(https?:\/\/)?(?:[\w-]+\.){1,}onion/i, "tor_link"],
];

function utcTimestamp(): string {
  return new Date().toISOString();
}

function extractPrompt(context: Record<string, unknown>): { prompt: string; issues: string[] } {
  const prompt = context.prompt;
  if (typeof prompt === "string") {
    return { prompt: prompt.replace(/\r\n/g, "\n"), issues: [] };
  }
  return { prompt: "", issues: ["missing_prompt"] };
}

function scanPrompt(prompt: string): string[] {
  const findings: string[] = [];
  if (!prompt.trim()) findings.push("empty_prompt");
  for (const [pattern, tag] of SUSPICIOUS_PATTERNS) {
    if (pattern.test(prompt)) findings.push(tag);
  }
  if ((prompt.match(/\n/g) ?? []).length > 100) findings.push("excessive_newlines");
  // Deduplicate preserving order
  return [...new Set(findings)];
}

function readRateTracker(): Record<string, number> {
  try {
    if (!existsSync(RATE_LIMIT_PATH)) return {};
    const content = JSON.parse(readFileSync(RATE_LIMIT_PATH, "utf-8"));
    if (typeof content !== "object" || content === null) return {};
    const out: Record<string, number> = {};
    for (const [k, v] of Object.entries(content)) {
      if (typeof v === "number") out[k] = v;
    }
    return out;
  } catch {
    return {};
  }
}

function writeRateTracker(data: Record<string, number>): void {
  try {
    const dir = dirname(RATE_LIMIT_PATH);
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
    writeFileSync(RATE_LIMIT_PATH, JSON.stringify(data, null, 2));
  } catch {
    // silent
  }
}

function checkRateLimit(userId: unknown, sessionId: unknown): string | null {
  const ref = String(userId ?? sessionId ?? "global");
  const now = Date.now() / 1000;
  const data = readRateTracker();
  const last = data[ref];
  data[ref] = now;
  writeRateTracker(data);
  if (typeof last === "number" && now - last < RATE_LIMIT_SECONDS) {
    return "rate_limited";
  }
  return null;
}

function recordSubmission(record: Record<string, unknown>): void {
  try {
    const dir = dirname(PROMPT_LOG_PATH);
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
    record.recordedAt = utcTimestamp();
    appendFileSync(PROMPT_LOG_PATH, JSON.stringify(record) + "\n");
  } catch {
    // silent
  }
}

function processPrompt(context: Record<string, unknown>): {
  payload: Record<string, unknown>;
  issues: string[];
  preview: string | null;
  shouldAlert: boolean;
} {
  let { prompt, issues } = extractPrompt(context);
  const metadata = typeof context.metadata === "object" && context.metadata !== null
    ? (context.metadata as Record<string, unknown>)
    : {};
  const userId = context.user_id ?? context.userId;
  const sessionId = context.session_id ?? context.sessionId;
  const timestamp = typeof context.timestamp === "string" ? context.timestamp : utcTimestamp();

  const rateIssue = checkRateLimit(userId, sessionId);
  if (rateIssue) issues.push(rateIssue);

  const suspicious = scanPrompt(prompt);
  issues.push(...suspicious);

  let truncated = false;
  let sanitized = prompt.trim();
  if (sanitized.length > MAX_PROMPT_LENGTH) {
    sanitized = sanitized.slice(0, MAX_PROMPT_LENGTH);
    truncated = true;
    issues.push("prompt_truncated");
  }

  // Deduplicate
  issues = [...new Set(issues)];

  const shouldAlert = issues.length > 0;
  const userPrompt: Record<string, unknown> = {
    prompt: sanitized,
    truncated,
    length: sanitized.length,
    timestamp,
  };
  if (userId) userPrompt.userId = String(userId);
  if (sessionId) userPrompt.sessionId = String(sessionId);
  if (Object.keys(metadata).length > 0) userPrompt.metadata = metadata;
  if (issues.length > 0) userPrompt.issues = issues;
  if (shouldAlert) userPrompt.requiresAttention = true;

  const preview = sanitized ? sanitized.slice(0, MAX_PREVIEW) : null;

  recordSubmission({
    timestamp,
    userId: userId ?? null,
    sessionId: sessionId ?? null,
    length: sanitized.length,
    issues,
  });

  return { payload: { userPrompt }, issues, preview, shouldAlert };
}

export function handleUserPromptSubmit(context: HookContext): HandlerResult {
  const payload = typeof context.payload === "object" && context.payload !== null ? context.payload : {};
  const { payload: processedPayload, issues, preview, shouldAlert } = processPrompt(payload);

  const base = (processedPayload.userPrompt ?? {}) as Record<string, unknown>;
  const ctx: Record<string, unknown> = {
    promptPreview: preview,
    issues: [...issues],
    timestamp: utcTimestamp(),
  };
  // Merge base fields excluding issues/requiresAttention
  for (const [k, v] of Object.entries(base)) {
    if (k !== "issues" && k !== "requiresAttention") {
      ctx[k] = v;
    }
  }

  const hr = createResult();
  hr.decisionPayload = { additionalContext: ctx };

  if (issues.length > 0) {
    hr.decisionPayload.decision = "block";
    hr.decisionPayload.reason =
      "Issues detected: " + issues.map((i) => i.replace(/_/g, " ")).join(", ");
    hr.continueValue = false;
  } else {
    hr.continueValue = true;
  }

  if (shouldAlert) {
    hr.audioType = USER_PROMPT_SUBMIT;
  } else {
    hr.suppressAudio = true;
  }

  return hr;
}
