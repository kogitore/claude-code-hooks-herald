#!/usr/bin/env bun
/**
 * Herald dispatcher — main entry point.
 *
 * Usage:
 *   bun run herald.ts --hook <Event>       (hook mode, reads stdin JSON)
 *   bun run herald.ts toggle|pause|...     (CLI mode)
 */

import * as constants from "./lib/constants";
import type { Handler, HookContext, HandlerResult } from "./lib/types";
import { playAudio, shouldThrottle, markEmitted, getThrottleWindow } from "./lib/audio";
import { isMuted } from "./lib/cli";
import { runCli } from "./lib/cli";
import { sendNotification, setTabTitle } from "./lib/notify";

// Handler imports
import { handleNotification } from "./handlers/notification";
import { handleStop, handleSubagentStop } from "./handlers/stop";
import { handlePreToolUse } from "./handlers/pre-tool-use";
import { handlePostToolUse } from "./handlers/post-tool-use";
import { handleSessionStart } from "./handlers/session-start";
import { handleSessionEnd } from "./handlers/session-end";
import { handleUserPromptSubmit } from "./handlers/user-prompt-submit";

const HANDLERS: Record<string, Handler> = {
  [constants.NOTIFICATION]: handleNotification,
  [constants.STOP]: handleStop,
  [constants.SUBAGENT_STOP]: handleSubagentStop,
  [constants.PRE_TOOL_USE]: handlePreToolUse,
  [constants.POST_TOOL_USE]: handlePostToolUse,
  [constants.SESSION_START]: handleSessionStart,
  [constants.SESSION_END]: handleSessionEnd,
  [constants.USER_PROMPT_SUBMIT]: handleUserPromptSubmit,
};

function readStdin(): Record<string, unknown> {
  try {
    // Bun reads stdin synchronously from file descriptor
    const buf = require("fs").readFileSync("/dev/stdin", "utf-8").trim();
    return buf ? JSON.parse(buf) : {};
  } catch {
    return {};
  }
}

function doPlayAudio(
  audioType: string | null,
  throttleKey: string | null,
  throttleWindow: number | null,
): void {
  if (!audioType) return;
  if (isMuted()) return;

  try {
    // Optional throttle
    if (throttleKey && typeof throttleWindow === "number" && throttleWindow > 0) {
      if (shouldThrottle(throttleKey, throttleWindow)) return;
    }

    // Use config-based throttle if handler didn't specify
    if (!throttleKey) {
      const configWindow = getThrottleWindow(audioType);
      if (configWindow > 0 && shouldThrottle(audioType, configWindow)) return;
    }

    const { played } = playAudio(audioType, true);

    if (played) {
      markEmitted(throttleKey ?? audioType);
    }
  } catch {
    // silent
  }
}

function dispatch(event: string, payload: Record<string, unknown>): Record<string, unknown> {
  const handler = HANDLERS[event];
  if (!handler) return { continue: true };

  const ctx: HookContext = {
    eventType: event,
    payload,
    decisionApi: null,
  };

  let result: HandlerResult;
  try {
    result = handler(ctx);
  } catch {
    return { continue: true };
  }

  // Audio
  const audioType = result.suppressAudio ? null : (result.audioType ?? event);
  doPlayAudio(audioType, result.throttleKey, result.throttleWindow);

  // Desktop notification (only for completion events)
  if (audioType) {
    try {
      sendNotification(event);
    } catch {
      // silent
    }
  }

  // Build response
  const response: Record<string, unknown> = { continue: result.continueValue };

  const dp = result.decisionPayload;
  if (dp) {
    if (event === constants.PRE_TOOL_USE) {
      const hso: Record<string, unknown> = {
        hookEventName: event,
        permissionDecision: (dp.permissionDecision as string) ?? "allow",
      };
      if (dp.permissionDecisionReason) {
        hso.permissionDecisionReason = dp.permissionDecisionReason;
      }
      response.hookSpecificOutput = hso;
    } else if (
      event === constants.POST_TOOL_USE ||
      event === constants.USER_PROMPT_SUBMIT ||
      event === constants.SESSION_START ||
      event === constants.SESSION_END
    ) {
      let addl = dp.additionalContext ?? "";
      if (typeof addl === "object") {
        try {
          addl = JSON.stringify(addl);
        } catch {
          addl = "";
        }
      }
      response.hookSpecificOutput = { hookEventName: event, additionalContext: addl };
    }

    if (dp.decision && event === constants.USER_PROMPT_SUBMIT) {
      response.decision = dp.decision;
      if (dp.reason) response.reason = dp.reason;
    }
  }

  // If handler already set hookSpecificOutput in response, keep it
  if (!response.hookSpecificOutput && typeof result.response === "object") {
    const existing = (result.response as Record<string, unknown>).hookSpecificOutput;
    if (existing) response.hookSpecificOutput = existing;
  }

  return response;
}

// --- Main ---

function main(): void {
  const args = process.argv.slice(2);

  // Check for --hook flag
  const hookIdx = args.indexOf("--hook");
  if (hookIdx !== -1 && args[hookIdx + 1]) {
    const event = args[hookIdx + 1];

    // Update tab title to working
    try {
      setTabTitle("working", event);
    } catch {
      // silent
    }

    const payload = readStdin();
    const out = dispatch(event, payload);
    try {
      process.stdout.write(JSON.stringify(out) + "\n");
    } catch {
      process.stdout.write('{"continue":true}\n');
    }
    return;
  }

  // CLI mode
  runCli(args);
}

main();
