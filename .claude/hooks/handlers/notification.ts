/**
 * Notification handler — simplest handler.
 */

import type { HookContext, HandlerResult } from "../lib/types";
import { createResult } from "../lib/types";
import { NOTIFICATION } from "../lib/constants";

export function handleNotification(_context: HookContext): HandlerResult {
  return createResult({ audioType: NOTIFICATION });
}
