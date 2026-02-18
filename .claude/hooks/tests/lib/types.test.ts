import { describe, test, expect } from "bun:test";
import { createResult } from "../../lib/types";

describe("createResult", () => {
  test("returns defaults", () => {
    const r = createResult();
    expect(r.response).toEqual({});
    expect(r.audioType).toBeNull();
    expect(r.throttleKey).toBeNull();
    expect(r.throttleWindow).toBeNull();
    expect(r.suppressAudio).toBe(false);
    expect(r.continueValue).toBe(true);
    expect(r.decisionPayload).toBeNull();
  });

  test("accepts overrides", () => {
    const r = createResult({ audioType: "Stop", continueValue: false });
    expect(r.audioType).toBe("Stop");
    expect(r.continueValue).toBe(false);
    expect(r.suppressAudio).toBe(false);
  });
});
