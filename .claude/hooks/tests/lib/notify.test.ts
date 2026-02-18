import { describe, test, expect } from "bun:test";
import { join } from "path";
import { mkdtempSync, writeFileSync, rmSync } from "fs";
import { tmpdir } from "os";
import {
  loadCustomMessages,
  formatEventMessage,
  DEFAULT_MESSAGES,
  NOTIFY_EVENTS,
} from "../../lib/notify";

describe("loadCustomMessages", () => {
  function makeTmpDir(): string {
    return mkdtempSync(join(tmpdir(), "herald-test-"));
  }

  test("loads valid messages.json", () => {
    const dir = makeTmpDir();
    const configPath = join(dir, "messages.json");
    writeFileSync(configPath, JSON.stringify({ messages: { Stop: "done!" } }));

    const result = loadCustomMessages(configPath);
    expect(result).toEqual({ Stop: "done!" });

    rmSync(dir, { recursive: true });
  });

  test("returns empty object when file does not exist", () => {
    const result = loadCustomMessages("/tmp/herald-nonexistent-config.json");
    expect(result).toEqual({});
  });

  test("returns empty object for invalid JSON", () => {
    const dir = makeTmpDir();
    const configPath = join(dir, "messages.json");
    writeFileSync(configPath, "not valid json {{{");

    const result = loadCustomMessages(configPath);
    expect(result).toEqual({});

    rmSync(dir, { recursive: true });
  });

  test("returns empty object when messages field is missing", () => {
    const dir = makeTmpDir();
    const configPath = join(dir, "messages.json");
    writeFileSync(configPath, JSON.stringify({ locale: "en" }));

    const result = loadCustomMessages(configPath);
    expect(result).toEqual({});

    rmSync(dir, { recursive: true });
  });
});

describe("formatEventMessage", () => {
  test("returns custom message for known event type", () => {
    const msg = formatEventMessage("Stop");
    // The module loads config/messages.json at init — should be zh-TW
    expect(msg).toBe("任務完成");
  });

  test("falls back to eventType string for unknown event", () => {
    const msg = formatEventMessage("UnknownEvent");
    expect(msg).toBe("UnknownEvent");
  });

  test("DEFAULT_MESSAGES covers all NOTIFY_EVENTS", () => {
    for (const event of NOTIFY_EVENTS) {
      expect(DEFAULT_MESSAGES[event]).toBeDefined();
    }
  });
});
