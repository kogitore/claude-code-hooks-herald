import { describe, test, expect } from "bun:test";
import { createDecisionApi } from "../../lib/decision";

describe("DecisionApi", () => {
  const api = createDecisionApi();

  describe("evaluateSafety", () => {
    test("allows safe commands", () => {
      const [d, r] = api.evaluateSafety("Bash", "ls -la");
      expect(d).toBe("allow");
      expect(r).toBeNull();
    });

    test("allows empty command", () => {
      const [d] = api.evaluateSafety("Bash", "");
      expect(d).toBe("allow");
    });

    test("denies rm -rf /", () => {
      const [d, r] = api.evaluateSafety("Bash", "rm -rf /");
      expect(d).toBe("deny");
      expect(r).toContain("Dangerous");
    });

    test("denies rm -rf *", () => {
      const [d] = api.evaluateSafety("Bash", "rm -rf *");
      expect(d).toBe("deny");
    });

    test("denies fork bomb", () => {
      const [d] = api.evaluateSafety("Bash", ":(){:|:&};:");
      expect(d).toBe("deny");
    });

    test("denies mkfs", () => {
      const [d] = api.evaluateSafety("Bash", "mkfs.ext4 /dev/sda1");
      expect(d).toBe("deny");
    });

    test("asks for rm in sensitive path", () => {
      const [d] = api.evaluateSafety("Bash", "rm /etc/passwd");
      expect(d).toBe("ask");
    });
  });

  describe("preToolUseDecision", () => {
    test("allows safe tool input", () => {
      const r = api.preToolUseDecision("Bash", { command: "echo hello" });
      expect(r.decision).toBe("allow");
      expect(r.blocked).toBe(false);
    });

    test("denies dangerous tool input", () => {
      const r = api.preToolUseDecision("Bash", { command: "rm -rf /" });
      expect(r.decision).toBe("deny");
      expect(r.blocked).toBe(true);
    });

    test("allows empty input", () => {
      const r = api.preToolUseDecision("Bash", {});
      expect(r.decision).toBe("allow");
    });
  });

  describe("postToolUseDecision", () => {
    test("allows successful result", () => {
      const r = api.postToolUseDecision("Bash", { exitCode: 0 });
      expect(r.decision).toBe("allow");
      expect(r.blocked).toBe(false);
    });

    test("blocks non-zero exit code", () => {
      const r = api.postToolUseDecision("Bash", { exitCode: 1 });
      expect(r.decision).toBe("block");
      expect(r.blocked).toBe(true);
    });

    test("blocks on tool error", () => {
      const r = api.postToolUseDecision("Bash", { toolError: "permission denied" });
      expect(r.decision).toBe("block");
      expect(r.blocked).toBe(true);
    });
  });

  describe("toDict", () => {
    test("returns correct structure", () => {
      const r = api.allow("test reason");
      const d = r.toDict();
      expect(d.decision).toBe("allow");
      expect(d.reason).toBe("test reason");
      expect(d.blocked).toBe(false);
      expect(d.permissionDecision).toBe("allow");
      expect(d.continue).toBe(true);
    });
  });
});
