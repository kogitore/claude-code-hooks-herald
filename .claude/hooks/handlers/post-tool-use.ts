/**
 * PostToolUse handler — audit and decision.
 */

import { existsSync, mkdirSync, appendFileSync } from "fs";
import { join, dirname } from "path";
import type { HookContext, HandlerResult, DecisionApi } from "../lib/types";
import { createResult } from "../lib/types";
import { POST_TOOL_USE } from "../lib/constants";
import { createDecisionApi } from "../lib/decision";
import { getRepoRoot } from "../lib/session";

const MAX_OUTPUT_SNIPPET = 600;
const AUDIT_LOG_PATH = join(getRepoRoot(), "logs", "tool_audit.jsonl");

function extractToolName(payload: Record<string, unknown>): string {
  for (const key of ["tool", "toolName", "tool_name", "name"]) {
    const val = payload[key];
    if (typeof val === "string" && val.trim()) return val.trim();
  }
  return "unknown";
}

function extractExitCode(result: Record<string, unknown>): number | null {
  const ec = result.exitCode ?? result.exit_code;
  if (typeof ec === "number") return ec;
  if (typeof ec === "string") {
    const n = parseInt(ec, 10);
    return isNaN(n) ? null : n;
  }
  return null;
}

function extractErrorMessage(result: Record<string, unknown>): string | null {
  for (const key of ["toolError", "error", "stderr", "traceback"]) {
    const v = result[key];
    if (typeof v === "string" && v.trim()) return v.trim();
  }
  return null;
}

function detectSuccess(result: Record<string, unknown>, exitCode: number | null): boolean {
  const s = result.success;
  if (typeof s === "boolean") return s;
  if (exitCode !== null) return exitCode === 0;
  const status = result.status;
  return typeof status === "string" && ["ok", "success", "completed"].includes(status.toLowerCase());
}

function sanitizeResult(result: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};

  if ("success" in result) out.success = Boolean(result.success);

  const outp = result.output;
  if (typeof outp === "string" && outp) {
    const s = outp.trim();
    out.outputPreview = s.slice(0, MAX_OUTPUT_SNIPPET);
    out.outputTruncated = s.length > MAX_OUTPUT_SNIPPET;
  }

  const err = extractErrorMessage(result);
  if (err) out.errorMessage = err.slice(0, MAX_OUTPUT_SNIPPET);

  const ec = extractExitCode(result);
  if (ec !== null) out.exitCode = ec;

  for (const k of ["stdout", "stderr"]) {
    if (k in result) out[k] = "<redacted>";
  }

  return out;
}

function utcTimestamp(): string {
  return new Date().toISOString();
}

function appendAudit(record: Record<string, unknown>): void {
  try {
    const dir = dirname(AUDIT_LOG_PATH);
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
    appendFileSync(AUDIT_LOG_PATH, JSON.stringify(record) + "\n");
  } catch {
    // silent
  }
}

export function handlePostToolUse(context: HookContext): HandlerResult {
  const payload = typeof context.payload === "object" && context.payload !== null ? context.payload : {};
  const api: DecisionApi = context.decisionApi ?? createDecisionApi();

  const tool = extractToolName(payload);
  let result = payload.result;
  if (typeof result !== "object" || result === null || Array.isArray(result)) {
    result = {};
  }
  const resultObj = result as Record<string, unknown>;

  const ec = extractExitCode(resultObj);
  const success = detectSuccess(resultObj, ec);
  const err = extractErrorMessage(resultObj);

  const decision = api.postToolUseDecision(tool, resultObj);

  const shouldAlert = !success || Boolean(err) || decision.blocked;
  const sanitized = sanitizeResult(resultObj) as Record<string, unknown> & { alerts?: string[] };

  if (decision.blocked) {
    if (!sanitized.alerts) sanitized.alerts = [];
    sanitized.alerts.push("decision_blocked");
  }
  if (err) {
    if (!sanitized.alerts) sanitized.alerts = [];
    sanitized.alerts.push("error_detected");
  }
  if (!success && !(sanitized.alerts ?? []).includes("error_detected")) {
    if (!sanitized.alerts) sanitized.alerts = [];
    sanitized.alerts.push("execution_failed");
  }

  const audit: Record<string, unknown> = {
    tool,
    timestamp: utcTimestamp(),
    result: sanitized,
  };
  if (ec !== null) audit.exitCode = ec;
  if (err) audit.errorMessage = err;

  decision.payload.additionalContext = audit;
  appendAudit({ ...audit, decision: decision.blocked ? "block" : "allow" });

  const hr = createResult();
  hr.decisionPayload = decision.toDict();
  hr.continueValue = !decision.blocked;

  if (shouldAlert) {
    hr.audioType = POST_TOOL_USE;
  } else {
    hr.suppressAudio = true;
  }

  return hr;
}
