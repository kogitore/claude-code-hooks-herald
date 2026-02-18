/**
 * Stop handler — handles both Stop and SubagentStop.
 */

import type { HookContext, HandlerResult } from "../lib/types";
import { createResult } from "../lib/types";

export function handleStop(context: HookContext): HandlerResult {
  return createResult({ audioType: context.eventType });
}

export function handleSubagentStop(context: HookContext): HandlerResult {
  return handleStop(context);
}
