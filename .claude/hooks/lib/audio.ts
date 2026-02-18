/**
 * Enhanced audio manager for Herald hooks.
 *
 * Features over Python version:
 * - Sound mappings support arrays (random selection, avoid consecutive repeats)
 * - Uses Bun.which() / Bun.spawn() / Bun.file()
 * - No locks needed (single-threaded JS)
 */

import { resolve, dirname, join } from "path";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "fs";

// Repo root: 3 levels up from lib/ → hooks/ → .claude/ → repo
const HOOKS_DIR = dirname(dirname(resolve(import.meta.dir)));
const REPO_ROOT = dirname(HOOKS_DIR);

const CONFIG_PATH = join(import.meta.dir, "..", "config", "audio.json");
const LAST_PLAYED_PATH = join(REPO_ROOT, "logs", "audio_last_played.json");

interface AudioConfig {
  basePath: string;
  mappings: Record<string, string[]>;
}

interface LoadedConfig {
  config: AudioConfig;
  volume: number;
  throttle: Record<string, number>;
}

function loadConfig(): LoadedConfig {
  const defaults: LoadedConfig = {
    config: { basePath: join(REPO_ROOT, ".claude", "sounds"), mappings: {} },
    volume: 0.2,
    throttle: {},
  };

  try {
    if (!existsSync(CONFIG_PATH)) return defaults;
    const data = JSON.parse(readFileSync(CONFIG_PATH, "utf-8"));

    const sf = data.sound_files;
    if (sf?.mappings) {
      for (const [k, v] of Object.entries(sf.mappings)) {
        // Backward compat: single string → 1-element array
        defaults.config.mappings[k] = Array.isArray(v) ? (v as string[]) : [v as string];
      }
    }

    const as = data.audio_settings;
    if (as) {
      defaults.volume = Number(as.volume ?? 0.2);
      if (as.throttle_seconds) {
        for (const [k, v] of Object.entries(as.throttle_seconds)) {
          defaults.throttle[k] = Number(v);
        }
      }
    }
  } catch {
    // Use defaults on any error
  }

  return defaults;
}

function selectPlayer(volume: number): { cmd: string | null; args: string[] } {
  // ENV override
  const envCmd = process.env.AUDIO_PLAYER_CMD;
  if (envCmd) {
    const envArgs = (process.env.AUDIO_PLAYER_ARGS ?? "").split(/\s+/).filter(Boolean);
    return { cmd: envCmd, args: envArgs };
  }

  const platform = process.platform;
  if (platform === "darwin") {
    if (Bun.which("afplay")) {
      return { cmd: "afplay", args: ["-v", volume.toFixed(3)] };
    }
  } else if (platform === "linux") {
    if (Bun.which("ffplay")) {
      return {
        cmd: "ffplay",
        args: ["-nodisp", "-autoexit", "-loglevel", "error", "-volume", String(Math.round(volume * 100))],
      };
    }
    if (Bun.which("aplay")) {
      return { cmd: "aplay", args: [] };
    }
  } else if (platform === "win32") {
    if (Bun.which("powershell")) {
      return { cmd: "powershell", args: ["-Command", "(New-Object System.Media.SoundPlayer '{0}').PlaySync()"] };
    }
  }

  return { cmd: null, args: [] };
}

// --- Last-played tracking for random selection ---
function loadLastPlayed(): Record<string, string> {
  try {
    if (existsSync(LAST_PLAYED_PATH)) {
      return JSON.parse(readFileSync(LAST_PLAYED_PATH, "utf-8"));
    }
  } catch {
    // ignore
  }
  return {};
}

function saveLastPlayed(data: Record<string, string>): void {
  try {
    const dir = dirname(LAST_PLAYED_PATH);
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
    writeFileSync(LAST_PLAYED_PATH, JSON.stringify(data, null, 2));
  } catch {
    // ignore
  }
}

function pickRandom(files: string[], audioType: string): string {
  if (files.length === 1) return files[0];

  const lastPlayed = loadLastPlayed();
  const last = lastPlayed[audioType];

  // Filter out last played to avoid repeats (if more than 1 option)
  const candidates = files.length > 1 ? files.filter((f) => f !== last) : files;
  const pick = candidates[Math.floor(Math.random() * candidates.length)];

  lastPlayed[audioType] = pick;
  saveLastPlayed(lastPlayed);

  return pick;
}

// --- Throttle tracking (in-memory Map, single-threaded) ---
const throttleData = new Map<string, number>();

export interface AudioContext {
  audioType: string;
  enabled: boolean;
  playerCmd: string | null;
  volume: number;
  status?: string;
  reason?: string;
  filePath?: string | null;
  returnCode?: number;
  error?: string;
  method?: string;
  [key: string]: unknown;
}

export function shouldThrottle(key: string, windowSeconds: number): boolean {
  const now = Date.now() / 1000;
  const last = throttleData.get(key) ?? 0;
  return now - last < windowSeconds;
}

export function markEmitted(key: string): void {
  throttleData.set(key, Date.now() / 1000);
}

export function resolveFile(audioType: string): string | null {
  const { config } = loadConfig();
  const files = config.mappings[audioType.trim()];
  if (!files || files.length === 0) return null;

  const filename = pickRandom(files, audioType.trim());
  const fullPath = join(config.basePath, filename);
  // Resolve relative to repo root
  const resolved = fullPath.startsWith("./") || !fullPath.startsWith("/") ? join(REPO_ROOT, fullPath) : fullPath;
  return existsSync(resolved) ? resolved : null;
}

export function playAudio(
  audioType: string,
  enabled = true,
  additionalContext?: Record<string, unknown>,
): { played: boolean; path: string | null; context: AudioContext } {
  const { volume } = loadConfig();
  const { cmd, args } = selectPlayer(volume);

  const context: AudioContext = {
    audioType,
    enabled,
    playerCmd: cmd,
    volume,
    ...(additionalContext ?? {}),
  };

  if (!enabled) {
    context.status = "skipped";
    context.reason = "disabled";
    return { played: false, path: null, context };
  }

  if (!cmd) {
    context.status = "skipped";
    context.reason = "no_player";
    return { played: false, path: null, context };
  }

  const path = resolveFile(audioType);
  context.filePath = path;

  if (!path) {
    context.status = "skipped";
    context.reason = "file_not_found";
    return { played: false, path, context };
  }

  try {
    let finalArgs: string[];
    if (cmd === "powershell") {
      finalArgs = args.map((a) => a.replace("{0}", path));
    } else {
      finalArgs = [...args, path];
    }

    const proc = Bun.spawnSync([cmd, ...finalArgs], {
      stdout: "ignore",
      stderr: "ignore",
      timeout: 3000,
    });

    const success = proc.exitCode === 0;
    context.status = success ? "played" : "failed";
    context.returnCode = proc.exitCode ?? undefined;
    return { played: success, path, context };
  } catch (e) {
    context.status = "failed";
    context.error = e instanceof Error ? e.message : String(e);
    return { played: false, path, context };
  }
}

// Convenience: get throttle config for an event
export function getThrottleWindow(audioType: string): number {
  const { throttle } = loadConfig();
  return throttle[audioType] ?? 0;
}

export function getVolume(): number {
  return loadConfig().volume;
}
