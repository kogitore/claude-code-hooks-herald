/**
 * PreToolUse handler — security gating.
 * Audio only for deny/ask; clean allows are silent.
 */

import type { HookContext, HandlerResult, DecisionApi, DecisionResult } from "../lib/types";
import { createResult } from "../lib/types";
import { PRE_TOOL_USE } from "../lib/constants";
import { createDecisionApi } from "../lib/decision";

const MAX_COMMAND_PREVIEW = 240;

function previewCommand(payload: Record<string, unknown>): string | null {
  const cmd = payload.command;
  if (typeof cmd === "string" && cmd.trim()) {
    return cmd.trim().slice(0, MAX_COMMAND_PREVIEW);
  }
  const args = payload.args;
  if (Array.isArray(args) && args.length > 0) {
    const joined = args.map(String).join(" ");
    return joined ? joined.slice(0, MAX_COMMAND_PREVIEW) : null;
  }
  return null;
}

function utcTimestamp(): string {
  return new Date().toISOString();
}

export function handlePreToolUse(context: HookContext): HandlerResult {
  const payload = typeof context.payload === "object" && context.payload !== null ? context.payload : {};
  const api: DecisionApi = context.decisionApi ?? createDecisionApi();

  const issues: string[] = [];

  // Extract tool name
  let tool = String(
    payload.tool ?? payload.toolName ?? payload.tool_name ?? payload.name ?? "unknown",
  );
  if (!tool.trim()) {
    tool = "unknown";
    issues.push("missing_tool_name");
  }

  // Extract and parse tool input
  const raw = payload.toolInput ?? payload.tool_input ?? payload.input;
  let toolInput: Record<string, unknown> | null = null;
  let preview: string | null = null;

  if (raw !== null && raw !== undefined) {
    if (typeof raw === "object" && !Array.isArray(raw)) {
      toolInput = raw as Record<string, unknown>;
      preview = previewCommand(toolInput);
    } else if (typeof raw === "string") {
      try {
        const parsed = JSON.parse(raw);
        if (typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)) {
          toolInput = parsed;
          preview = previewCommand(parsed);
        } else if (Array.isArray(parsed)) {
          toolInput = { args: parsed };
          preview = previewCommand(toolInput);
        } else {
          issues.push("unsupported_tool_input_type");
          preview = raw.slice(0, MAX_COMMAND_PREVIEW);
        }
      } catch {
        issues.push("invalid_tool_input_json");
        preview = raw.slice(0, MAX_COMMAND_PREVIEW);
      }
    } else if (Array.isArray(raw)) {
      toolInput = { args: raw.map(String) };
      preview = previewCommand(toolInput);
    } else {
      issues.push("unsupported_tool_input_type");
      preview = String(raw).slice(0, MAX_COMMAND_PREVIEW);
    }
  }

  // Evaluate safety
  let decision: DecisionResult;
  try {
    decision = api.preToolUseDecision(tool, toolInput ?? {});
  } catch (e) {
    decision = api.ask("無法評估工具安全性，請人工確認", PRE_TOOL_USE);
  }

  // If not blocked but has issues, escalate to ask
  if (!decision.blocked && issues.length > 0) {
    decision = api.ask("工具輸入格式不明確，請人工確認", PRE_TOOL_USE);
  }

  // Enrich payload
  const extra = (decision.payload.additionalContext ?? {}) as Record<string, unknown>;
  if (!extra.tool) extra.tool = tool;
  if (issues.length > 0 && !extra.issues) extra.issues = issues;
  decision.payload.additionalContext = extra;

  const audit: Record<string, unknown> = {
    decision: decision.payload.permissionDecision ?? decision.payload.decision ?? "unknown",
    blocked: decision.blocked,
    timestamp: utcTimestamp(),
  };
  if (preview) audit.commandPreview = preview;
  if (!decision.payload.preToolUseAudit) decision.payload.preToolUseAudit = audit;

  // Build result
  const hr = createResult();
  hr.decisionPayload = decision.toDict();
  hr.continueValue = !decision.blocked;

  const perm = decision.payload.permissionDecision;
  if (perm === "allow" && !decision.blocked) {
    hr.suppressAudio = true;
  } else {
    hr.audioType = PRE_TOOL_USE;
  }

  return hr;
}
