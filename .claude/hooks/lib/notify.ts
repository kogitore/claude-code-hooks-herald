/**
 * Desktop notification system for Herald hooks.
 *
 * - macOS: JXA overlay → terminal-notifier → osascript fallback
 * - Linux: notify-send
 * - Terminal tab title updates (all platforms, stderr)
 * - iTerm2 OSC 9 notification
 *
 * Only triggered on completion events: Stop, SubagentStop, Notification, SessionEnd.
 */

import { basename } from "path";

const NOTIFY_EVENTS = new Set(["Stop", "SubagentStop", "Notification", "SessionEnd"]);

/** Get project name from cwd */
function projectName(): string {
  return basename(process.cwd());
}

// --- Tab title (writes to stderr so stdout stays clean for JSON) ---

export function setTabTitle(status: "working" | "done" | "error", detail?: string): void {
  const project = projectName();
  const icon = status === "working" ? "\u25CF" : status === "done" ? "\u2713" : "\u2717";
  const suffix = detail ? `: ${detail}` : "";
  const title = `${icon} ${project}${suffix}`;

  // Standard terminal title escape sequence
  process.stderr.write(`\x1b]0;${title}\x07`);

  // iTerm2 tab title
  process.stderr.write(`\x1b]1;${title}\x07`);
}

// --- iTerm2 OSC 9 notification ---

function iterm2Notify(message: string): void {
  process.stderr.write(`\x1b]9;${message}\x07`);
}

// --- macOS notifications ---

function macJxaNotify(title: string, message: string): boolean {
  try {
    const script = `
      var app = Application.currentApplication();
      app.includeStandardAdditions = true;
      app.displayNotification("${message.replace(/"/g, '\\"')}", {
        withTitle: "${title.replace(/"/g, '\\"')}",
        soundName: "default"
      });
    `;
    const proc = Bun.spawnSync(["osascript", "-l", "JavaScript", "-e", script], {
      stdout: "ignore",
      stderr: "ignore",
      timeout: 3000,
    });
    return proc.exitCode === 0;
  } catch {
    return false;
  }
}

function terminalNotifierNotify(title: string, message: string): boolean {
  if (!Bun.which("terminal-notifier")) return false;
  try {
    const proc = Bun.spawnSync(
      ["terminal-notifier", "-title", title, "-message", message, "-group", "herald"],
      { stdout: "ignore", stderr: "ignore", timeout: 3000 },
    );
    return proc.exitCode === 0;
  } catch {
    return false;
  }
}

function osascriptNotify(title: string, message: string): boolean {
  try {
    const script = `display notification "${message.replace(/"/g, '\\"')}" with title "${title.replace(/"/g, '\\"')}"`;
    const proc = Bun.spawnSync(["osascript", "-e", script], {
      stdout: "ignore",
      stderr: "ignore",
      timeout: 3000,
    });
    return proc.exitCode === 0;
  } catch {
    return false;
  }
}

// --- Linux notification ---

function linuxNotify(title: string, message: string): boolean {
  if (!Bun.which("notify-send")) return false;
  try {
    const proc = Bun.spawnSync(["notify-send", title, message, "--expire-time=5000"], {
      stdout: "ignore",
      stderr: "ignore",
      timeout: 3000,
    });
    return proc.exitCode === 0;
  } catch {
    return false;
  }
}

// --- Public API ---

export function sendNotification(eventType: string, detail?: string): boolean {
  if (!NOTIFY_EVENTS.has(eventType)) return false;

  const project = projectName();
  const title = `Herald: ${project}`;
  const message = detail ?? formatEventMessage(eventType);

  // Update tab title
  const tabStatus = eventType === "SessionEnd" ? "done" : eventType === "Stop" ? "done" : "done";
  setTabTitle(tabStatus, eventType);

  // iTerm2 inline notification
  iterm2Notify(`${title} — ${message}`);

  // Platform-specific desktop notification
  const platform = process.platform;
  if (platform === "darwin") {
    // Try JXA first (most visible), then terminal-notifier, then osascript
    return macJxaNotify(title, message) || terminalNotifierNotify(title, message) || osascriptNotify(title, message);
  } else if (platform === "linux") {
    return linuxNotify(title, message);
  }

  return false;
}

function formatEventMessage(eventType: string): string {
  switch (eventType) {
    case "Stop":
      return "Task completed";
    case "SubagentStop":
      return "Sub-agent completed";
    case "Notification":
      return "Notification received";
    case "SessionEnd":
      return "Session ended";
    default:
      return eventType;
  }
}
