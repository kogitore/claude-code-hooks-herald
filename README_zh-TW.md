<div align="center">

[English](./README.md) | [繁體中文](./README_zh-TW.md)

**Changelog:** see [CHANGELOG.md](./CHANGELOG.md) · **Design/Notes:** see [/updates](./updates/)

</div>

> 本專案啟發自 [disler/claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery)

# Claude Code Hooks Herald

一套為 Claude Code 提供音效回饋的 Hook 集合，專注於本機 `.wav` 檔播放，無需任何雲端 TTS 或 API Key。

## 功能

- 🔔 通知音效：在使用者互動時播放提示
- ✅ 任務完成音效：工作完成即刻回饋
- 🎯 子代理完成音效：分工流程有清晰聲音標記
- ⏱️ 智慧節流：避免重複播放造成干擾
- 🎵 純本機音效檔：無外部依賴、離線可用

## 快速開始

本專案無需複雜安裝，最精簡的啟用步驟如下：

1.  **安裝 uv（建議）**：本專案使用 [uv](https://docs.astral.sh/uv/) 來快速執行 Python 腳本。透過以下指令安裝：
    ```bash
    curl -LsSf https://astral.sh/install.sh | sh
    ```
    或者，您也可以在下方所有指令中將 `uv run` 替換為 `python3`。

2.  **提供音效檔**：將您的 `.wav` 音效檔放入 `.claude/sounds/` 資料夾中。

3.  **正確命名**：確保檔案名稱與設定中所預期的名稱相符（例如 `user_prompt.wav`, `task_complete.wav`）。

這樣就完成了！掛鉤系統將會自動偵測並播放音效。如需進階修改，請參考下方的設定說明。

## 前置需求

- **Python 3.10 以上**：目前程式僅使用標準函式庫。
- **[uv](https://docs.astral.sh/uv/)**：本文件中的指令預設透過 uv 直接執行腳本，可用 `curl -LsSf https://astral.sh/install.sh | sh` 安裝；若不想安裝 uv，可將指令改為 `python3 .claude/hooks/<script>.py ...`。
- **系統音效工具**：macOS 內建 `afplay`；Linux 需預先安裝 `ffplay`（FFmpeg）或 `aplay`（ALSA）；Windows 使用內建的 `winsound` 模組。

## 設定

音效設定由 `.claude/hooks/utils/audio_config.json` 管理：

```json
{
  "audio_settings": {
    "enabled": true,
    "mode": "audio_files",
    "volume": 0.2
  },
  "sound_files": {
    "base_path": "./.claude/sounds",
    "mappings": {
      "stop": "task_complete.wav",
      "agent_stop": "agent_complete.wav",
      "subagent_stop": "agent_complete.wav",
      "user_notification": "user_prompt.wav"
    }
  }
}
```

## 音效檔

請在 `.claude/sounds/` 放置以下 `.wav` 檔：
- `task_complete.wav`：任務完成播放
- `agent_complete.wav`：子代理完成播放
- `user_prompt.wav`：一般通知播放

## 測試

從專案根目錄執行 pytest（可用 uv 免安裝執行）：

```
# 方式 A：使用 uv 執行 pytest（無需安裝全域套件）
uvx pytest -q .claude/hooks/tests

# 方式 B：本機安裝後執行
pip install -U pytest && pytest -q .claude/hooks/tests
```

說明：
- 測試預設以 `AUDIO_PLAYER_CMD=true` 模擬播放器成功，不需系統音效。
- 若要實測播放，請移除該環境變數並在 `.claude/sounds/` 放入對應 wav 檔。

## 授權

MIT License（詳見 LICENSE）

## 致謝

本專案受 Claude Code hook 系統範例及 [claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery) 專案啟發。

## 輸出與環境變數

- JSON 單一輸出：每個 hook 只會輸出一段 JSON（`hookSpecificOutput`）。

```
{"hookSpecificOutput": {"hookEventName": "UserNotification", "status": "completed", "audioPlayed": true, "throttled": false, "notes": []}}
```

- 音效路徑覆寫：可用環境變數指定音效資料夾（優先於設定檔）
  - `CLAUDE_SOUNDS_DIR` 或 `AUDIO_SOUNDS_DIR`
  - 範例：

```
export CLAUDE_SOUNDS_DIR="/absolute/path/to/sounds"
```

## 常用指令範例

- 用戶通知（啟用音效）：

```
echo '{}' | uv run .claude/hooks/notification.py --enable-audio
# 或
echo '{}' | python3 .claude/hooks/notification.py --enable-audio
```

- 任務完成（啟用音效）：

```
echo '{}' | uv run .claude/hooks/stop.py --enable-audio
# 或
echo '{}' | python3 .claude/hooks/stop.py --enable-audio
```

- 子代理完成（啟用音效）：

```
echo '{}' | uv run .claude/hooks/subagent_stop.py --enable-audio
# 或
echo '{}' | python3 .claude/hooks/subagent_stop.py --enable-audio
```
