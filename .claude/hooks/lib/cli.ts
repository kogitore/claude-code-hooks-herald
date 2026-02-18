/**
 * CLI control commands for Herald.
 *
 * herald toggle   — Toggle mute on/off
 * herald pause    — Pause (mute)
 * herald resume   — Resume (unmute)
 * herald status   — Show current state
 * herald preview [event] — Play sample sound
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from "fs";
import { dirname, join, resolve } from "path";
import { playAudio, getVolume } from "./audio";
import { ALL_EVENTS } from "./constants";

const HOOKS_DIR = dirname(dirname(resolve(import.meta.dir)));
const REPO_ROOT = dirname(HOOKS_DIR);
const STATE_PATH = join(REPO_ROOT, "logs", "herald_state.json");

export interface HeraldState {
  muted: boolean;
  mutedAt: string | null;
}

export function loadHeraldState(): HeraldState {
  try {
    if (existsSync(STATE_PATH)) {
      const data = JSON.parse(readFileSync(STATE_PATH, "utf-8"));
      return {
        muted: Boolean(data.muted),
        mutedAt: data.mutedAt ?? null,
      };
    }
  } catch {
    // ignore
  }
  return { muted: false, mutedAt: null };
}

export function saveHeraldState(state: HeraldState): void {
  try {
    const dir = dirname(STATE_PATH);
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
    writeFileSync(STATE_PATH, JSON.stringify(state, null, 2));
  } catch {
    // ignore
  }
}

export function isMuted(): boolean {
  return loadHeraldState().muted;
}

function toggle(): void {
  const state = loadHeraldState();
  state.muted = !state.muted;
  state.mutedAt = state.muted ? new Date().toISOString() : null;
  saveHeraldState(state);
  console.log(state.muted ? "Herald: muted" : "Herald: unmuted");
}

function pause(): void {
  const state = loadHeraldState();
  if (state.muted) {
    console.log("Herald: already muted");
    return;
  }
  state.muted = true;
  state.mutedAt = new Date().toISOString();
  saveHeraldState(state);
  console.log("Herald: muted");
}

function resume(): void {
  const state = loadHeraldState();
  if (!state.muted) {
    console.log("Herald: already active");
    return;
  }
  state.muted = false;
  state.mutedAt = null;
  saveHeraldState(state);
  console.log("Herald: resumed");
}

function status(): void {
  const state = loadHeraldState();
  const vol = getVolume();
  console.log("Herald Status");
  console.log("─────────────");
  console.log(`Muted:   ${state.muted ? "yes" : "no"}`);
  if (state.mutedAt) console.log(`Since:   ${state.mutedAt}`);
  console.log(`Volume:  ${vol}`);
  console.log(`Events:  ${ALL_EVENTS.join(", ")}`);
}

function preview(event?: string): void {
  const target = event ?? "Notification";
  if (!ALL_EVENTS.includes(target as any)) {
    console.error(`Unknown event: ${target}`);
    console.error(`Available: ${ALL_EVENTS.join(", ")}`);
    process.exit(1);
  }
  console.log(`Playing preview for: ${target}`);
  const { played, path, context } = playAudio(target, true);
  if (played) {
    console.log(`Played: ${path}`);
  } else {
    console.log(`Could not play: ${context.reason ?? context.error ?? "unknown"}`);
  }
}

export function runCli(args: string[]): void {
  const command = args[0];
  switch (command) {
    case "toggle":
      toggle();
      break;
    case "pause":
      pause();
      break;
    case "resume":
      resume();
      break;
    case "status":
      status();
      break;
    case "preview":
      preview(args[1]);
      break;
    default:
      console.log("Herald CLI");
      console.log("──────────");
      console.log("Commands:");
      console.log("  toggle            Toggle mute on/off");
      console.log("  pause             Mute all sounds");
      console.log("  resume            Unmute sounds");
      console.log("  status            Show current state");
      console.log("  preview [event]   Play sample sound");
      break;
  }
}
