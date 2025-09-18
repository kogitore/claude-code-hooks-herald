> **[中文版本](./windows-volume-control_zh-TW.md)**

# Experiment: Windows Volume Control

## Hypothesis
A pure-Python approach can deliver per-hook volume control on Windows without touching global system volume or adding third-party dependencies.

## Setup
- Platform: Windows 11 (22H2)
- Python: 3.11 with standard library only
- Test audio: 2–3 second WAV samples shipped in `sounds/`
- Environment override: `AUDIO_PLAYER_CMD` unset to force real playback

## Procedure
1. Compare third-party libraries (`pygame`, `pydub`, `sounddevice`) for volume support.
2. Evaluate Windows Core Audio APIs via `ctypes`.
3. Prototype WAV preprocessing (pre-rendered gain variants).
4. Implement in-memory resampling with `audioop` + `wave` + `io` and play via `winsound.PlaySound(..., SND_MEMORY)`.
5. Measure latency and verify fallback behaviour when errors occur.

## Results
- ✅ Volume scaling 0.2, 0.5, 1.0 works with audible differences.
- ✅ Processing time < 50 ms for short clips; no temp files generated.
- ✅ Error handling: corrupted WAV triggers graceful fallback to original playback.
- ❌ Limited to WAV format; large files consume additional RAM during buffering.

## Analysis
In-memory processing satisfies the zero-dependency constraint while keeping latency within hook budgets. Although CPU and memory usage grow with file size, hook audio clips are short enough that the trade-off is acceptable.

## Next Steps
- Monitor memory usage on long sessions with repeated playback.
- Explore optional fallback to external players if future hooks require non-WAV assets.
- Document troubleshooting tips for `winsound` failures (e.g., missing multimedia services).
