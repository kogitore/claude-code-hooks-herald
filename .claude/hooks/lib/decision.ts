/**
 * Decision API — safety evaluation for tool use.
 * Port of decision_api.py with KISS approach.
 */

import type { DecisionApi, DecisionResult } from "./types";

const DANGEROUS_PATTERNS = [
  /\brm\s+-rf\s+\//i,
  /\brm\s+-rf\s+\*/i,
  />\s*\/dev\/sd[a-z]/i,
  /\bdd\s+.*of=\/dev\/sd[a-z]/i,
  /:\(\)\{.*\}/,
  /\bmkfs\./i,
  /\bfdisk\s+\/dev/i,
];

const DESTRUCTIVE_KEYWORDS = ["rm ", "rmdir ", "del ", "format ", "fdisk ", "mkfs."];
const SENSITIVE_PATHS = ["/", "/bin", "/usr", "/etc", "/var", "/sys"];

function createDecisionResult(
  decision: string,
  reason: string,
  blocked: boolean,
  extra: Record<string, unknown> = {},
): DecisionResult {
  return {
    decision,
    reason,
    blocked,
    additionalContext: extra,
    payload: {
      permissionDecision: decision,
      permissionDecisionReason: reason,
      decision,
      continue: !blocked,
      additionalContext: extra,
    },
    toDict() {
      return {
        decision: this.decision,
        reason: this.reason,
        blocked: this.blocked,
        permissionDecision: this.decision,
        permissionDecisionReason: this.reason,
        continue: !this.blocked,
        additionalContext: this.additionalContext,
      };
    },
  };
}

export function createDecisionApi(): DecisionApi {
  function evaluateSafety(toolName: string, command: string): [string, string | null] {
    if (!command || typeof command !== "string") return ["allow", null];
    const cmd = command.trim();

    for (const pattern of DANGEROUS_PATTERNS) {
      if (pattern.test(cmd)) {
        return ["deny", `Dangerous command pattern detected: ${pattern.source}`];
      }
    }

    const lower = cmd.toLowerCase();
    for (const keyword of DESTRUCTIVE_KEYWORDS) {
      if (lower.includes(keyword)) {
        for (const path of SENSITIVE_PATHS) {
          if (cmd.includes(path)) {
            return ["ask", `Potentially destructive command affecting system path: ${path}`];
          }
        }
      }
    }

    return ["allow", null];
  }

  function preToolUseDecision(toolName: string, toolInput: Record<string, unknown>): DecisionResult {
    if (!toolInput) return allow("No tool input to evaluate", "PreToolUse");
    const command = (toolInput.command ?? "") as string;
    if (!command) return allow("No command to evaluate", "PreToolUse");

    const [decision, reason] = evaluateSafety(toolName, command);
    if (decision === "deny") return deny(reason ?? "Dangerous command detected", "PreToolUse");
    if (decision === "ask") return ask(reason ?? "Command requires confirmation", "PreToolUse");
    return allow("Command is safe", "PreToolUse");
  }

  function postToolUseDecision(toolName: string, result: Record<string, unknown>): DecisionResult {
    // Post tool use: check result for errors
    const exitCode = result.exitCode ?? result.exit_code;
    if (typeof exitCode === "number" && exitCode !== 0) {
      return createDecisionResult("block", `Non-zero exit code: ${exitCode}`, true);
    }
    const err = result.toolError ?? result.error;
    if (typeof err === "string" && err.trim()) {
      return createDecisionResult("block", `Tool error: ${err.trim().slice(0, 200)}`, true);
    }
    return allow("Tool executed successfully");
  }

  function allow(reason: string, _event = ""): DecisionResult {
    return createDecisionResult("allow", reason, false);
  }

  function deny(reason: string, _event = ""): DecisionResult {
    return createDecisionResult("deny", reason, true);
  }

  function ask(reason: string, _event = ""): DecisionResult {
    return createDecisionResult("ask", reason, false);
  }

  return { evaluateSafety, preToolUseDecision, postToolUseDecision, allow, deny, ask };
}
