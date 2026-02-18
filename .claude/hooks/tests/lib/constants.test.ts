import { describe, test, expect } from "bun:test";
import { ALL_EVENTS, PRE_TOOL_USE, POST_TOOL_USE, SESSION_START, SESSION_END, USER_PROMPT_SUBMIT, NOTIFICATION, STOP, SUBAGENT_STOP, PRE_COMPACT } from "../../lib/constants";

describe("constants", () => {
  test("all event names are defined", () => {
    expect(PRE_TOOL_USE).toBe("PreToolUse");
    expect(POST_TOOL_USE).toBe("PostToolUse");
    expect(SESSION_START).toBe("SessionStart");
    expect(SESSION_END).toBe("SessionEnd");
    expect(USER_PROMPT_SUBMIT).toBe("UserPromptSubmit");
    expect(NOTIFICATION).toBe("Notification");
    expect(STOP).toBe("Stop");
    expect(SUBAGENT_STOP).toBe("SubagentStop");
    expect(PRE_COMPACT).toBe("PreCompact");
  });

  test("ALL_EVENTS contains 9 events", () => {
    expect(ALL_EVENTS).toHaveLength(9);
  });

  test("ALL_EVENTS includes all known events", () => {
    for (const e of [PRE_TOOL_USE, POST_TOOL_USE, SESSION_START, SESSION_END, USER_PROMPT_SUBMIT, NOTIFICATION, STOP, SUBAGENT_STOP, PRE_COMPACT]) {
      expect(ALL_EVENTS).toContain(e);
    }
  });
});
