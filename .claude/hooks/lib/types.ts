/**
 * Core types for Herald hooks.
 */

export interface HandlerResult {
  response: Record<string, unknown>;
  audioType: string | null;
  throttleKey: string | null;
  throttleWindow: number | null;
  suppressAudio: boolean;
  continueValue: boolean;
  decisionPayload: Record<string, unknown> | null;
}

export function createResult(overrides?: Partial<HandlerResult>): HandlerResult {
  return {
    response: {},
    audioType: null,
    throttleKey: null,
    throttleWindow: null,
    suppressAudio: false,
    continueValue: true,
    decisionPayload: null,
    ...overrides,
  };
}

export interface HookContext {
  eventType: string;
  payload: Record<string, unknown>;
  decisionApi: DecisionApi | null;
}

export interface DecisionApi {
  evaluateSafety(toolName: string, command: string): [string, string | null];
  preToolUseDecision(toolName: string, toolInput: Record<string, unknown>): DecisionResult;
  postToolUseDecision(toolName: string, result: Record<string, unknown>): DecisionResult;
  allow(reason: string, event?: string): DecisionResult;
  deny(reason: string, event?: string): DecisionResult;
  ask(reason: string, event?: string): DecisionResult;
}

export interface DecisionResult {
  decision: string;
  reason: string;
  blocked: boolean;
  additionalContext: Record<string, unknown>;
  payload: Record<string, unknown>;
  toDict(): Record<string, unknown>;
}

export type Handler = (context: HookContext) => HandlerResult;
