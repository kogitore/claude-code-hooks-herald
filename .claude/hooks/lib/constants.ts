/**
 * Centralised constants for Claude Code hook event names.
 */

export const PRE_TOOL_USE = "PreToolUse" as const;
export const POST_TOOL_USE = "PostToolUse" as const;
export const SESSION_START = "SessionStart" as const;
export const SESSION_END = "SessionEnd" as const;
export const USER_PROMPT_SUBMIT = "UserPromptSubmit" as const;
export const NOTIFICATION = "Notification" as const;
export const STOP = "Stop" as const;
export const SUBAGENT_STOP = "SubagentStop" as const;
export const PRE_COMPACT = "PreCompact" as const;

export const ALL_EVENTS = [
  NOTIFICATION,
  STOP,
  SUBAGENT_STOP,
  PRE_TOOL_USE,
  POST_TOOL_USE,
  USER_PROMPT_SUBMIT,
  SESSION_START,
  SESSION_END,
  PRE_COMPACT,
] as const;

export type EventName = (typeof ALL_EVENTS)[number];
