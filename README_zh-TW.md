<div align="center">

[English](./README.md) | [繁體中文](./README_zh-TW.md)

**更新日誌：** 見 [CHANGELOG.md](./CHANGELOG.md) · **設計筆記：** 見 [/updates](./updates/)

</div>

> 本專案啟發自 [disler/claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery)

# Herald Hooks

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) 的統一 Hooks 調度器。透過單一 TypeScript 入口處理所有官方 hook 事件，提供本機音效回饋（含節流）、桌面通知，以及可設定的工具安全策略。

## 功能

- **單一調度器** — 一個入口（`herald.ts`）處理全部 8 個已實作的 Claude Code 事件。
- **Decision API** — 支援 Allow / Deny / Ask，透過 `decision-policy.json` 設定規則。
- **音效回饋** — 本機 `.wav` 播放，依事件類型節流。支援多音效隨機選擇。
- **桌面通知** — macOS / Linux / Windows，支援 i18n 訊息自訂。
- **終端機標題** — 更新 Terminal / iTerm2 分頁標題，顯示目前事件狀態。
- **Session 追蹤** — 檔案式狀態管理與 JSONL 事件紀錄。
- **CLI 控制** — `toggle`、`pause`、`resume`、`status`、`preview` 指令。
- **零依賴** — 僅使用 Bun 內建模組（`fs`、`path`、`child_process`）。

## 快速開始

### 系統需求

- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code)
- [Bun](https://bun.sh/) 執行環境

**音效系統（播放音效用）：**
- **macOS：** `afplay`（內建）
- **Linux：** `ffplay`（ffmpeg）或 `aplay`（alsa-utils）
- **Windows：** PowerShell `[System.Media.SoundPlayer]`（內建）

### 安裝

```bash
git clone https://github.com/user/herald-hooks.git
cd herald-hooks
```

將 hook 設定複製到你的 Claude Code 專案：

```bash
cp .claude/settings.json /path/to/your/project/.claude/settings.json
```

> 或者，將 `.claude/settings.json` 中的 `hooks` 區段合併到你現有的設定檔。

### 放入音效檔

將 `.wav` 檔案放入 `.claude/sounds/`：

```
.claude/sounds/
├── task_complete.wav    # Stop / PostToolUse / SessionEnd
├── agent_complete.wav   # SubagentStop
└── user_prompt.wav      # Notification / PreToolUse / SessionStart / UserPromptSubmit
```

詳細說明請見 `.claude/sounds/README.md`。

### 驗證

```bash
# 測試通知
echo '{"message": "test"}' | bun run .claude/hooks/herald.ts --hook Notification

# 測試安全策略（應被拒絕）
echo '{"tool": "Bash", "input": {"command": "rm -rf /"}}' | bun run .claude/hooks/herald.ts --hook PreToolUse
```

**預期輸出：**
- Notification：`{"continue":true}` + 音效播放
- 安全測試：`{"continue":false, ...}`（危險指令被阻擋）

## 設定

### 音效（`config/audio.json`）

```json
{
  "sound_files": {
    "base_path": "./.claude/sounds",
    "mappings": {
      "Stop": ["task_complete.wav"],
      "SubagentStop": ["agent_complete.wav"],
      "Notification": ["user_prompt.wav"]
    }
  },
  "audio_settings": {
    "volume": 0.2,
    "throttle_seconds": {
      "Stop": 120,
      "Notification": 30
    }
  }
}
```

透過環境變數覆寫音效目錄：

```bash
export CLAUDE_SOUNDS_DIR="/absolute/path/to/sounds"
```

### Decision Policy（`config/decision-policy.json`）

PreToolUse / PostToolUse / Stop 事件的安全規則：

```json
{
  "pre_tool_use": {
    "rules": [
      {
        "action": "deny",
        "pattern": "rm\\s+-rf\\s+/",
        "reason": "危險命令：刪除根目錄",
        "tags": ["system:dangerous"],
        "severity": "critical"
      },
      {
        "action": "ask",
        "tags": ["git:destructive"],
        "reason": "請確認是否需要清除所有修改",
        "severity": "high"
      }
    ]
  }
}
```

**內建標籤：**

| 標籤 | 說明 | 嚴重度 |
|------|------|--------|
| `system:dangerous` | 破壞性指令（`rm -rf /`、`shutdown`） | critical |
| `git:destructive` | 重設工作區的 Git 指令（`reset --hard`、`clean -fd`） | high |
| `secrets:file` | 憑證檔案（`.env`、`id_rsa`、`*.pem`） | high |
| `package:install` | 套件安裝（`npm install`、`pip install`） | medium |
| `dependency:lock` | 鎖定檔（`package-lock.json`、`poetry.lock`） | medium |

### i18n 訊息（`config/messages.json`）

自訂各語系的通知訊息：

```json
{
  "locale": "zh-TW",
  "messages": {
    "Stop": "任務完成",
    "SubagentStop": "子代理完成",
    "Notification": "收到通知",
    "SessionEnd": "工作階段結束"
  }
}
```

## CLI

```bash
bun run .claude/hooks/herald.ts toggle            # 切換靜音
bun run .claude/hooks/herald.ts pause             # 靜音
bun run .claude/hooks/herald.ts resume            # 取消靜音
bun run .claude/hooks/herald.ts status            # 顯示目前狀態
bun run .claude/hooks/herald.ts preview [event]   # 播放測試音效
```

## 支援事件

| 事件 | 說明 |
|------|------|
| `Notification` | 一般通知 |
| `Stop` | 任務完成 |
| `SubagentStop` | 子代理完成 |
| `PreToolUse` | 工具執行前安全檢查 |
| `PostToolUse` | 工具執行後稽核 |
| `UserPromptSubmit` | 提示詞驗證與頻率限制 |
| `SessionStart` | Session 初始化與健康檢查 |
| `SessionEnd` | 清理與狀態歸檔 |

> `PreCompact` 已定義但尚未實作。

## 測試

```bash
bun test
```

測試使用 `AUDIO_PLAYER_CMD=true`（空操作），不需要系統音效。

## 專案結構

```
.claude/
├── hooks/
│   ├── herald.ts              # 主調度器
│   ├── lib/                   # 核心函式庫
│   │   ├── audio.ts           # 音效播放 + 節流
│   │   ├── notify.ts          # 桌面通知 + 終端機標題
│   │   ├── decision.ts        # 安全評估
│   │   ├── cli.ts             # CLI 指令
│   │   ├── session.ts         # Session 狀態 + 事件紀錄
│   │   ├── constants.ts       # 事件類型常數
│   │   └── types.ts           # 型別定義
│   ├── handlers/              # 事件處理器
│   ├── config/                # JSON 設定檔
│   └── tests/                 # 測試套件
├── sounds/                    # 音效檔案（.wav）
├── logs/                      # 執行紀錄與 Session 資料
└── settings.json              # Claude Code hook 路由設定
```

## 疑難排解

| 問題 | 解決方法 |
|------|----------|
| 沒有音效 | 確認 `.claude/sounds/` 有 `.wav` 檔案 |
| Linux 無音效 | `sudo apt-get install ffmpeg` 或 `alsa-utils` |
| Hooks 未偵測到 | 確認 `.claude/settings.json` 在專案根目錄 |
| 找不到 Bun | [安裝 Bun](https://bun.sh/) 並確認在 `$PATH` 中 |

## 免責聲明

本專案為獨立的社群驅動專案，**與 Anthropic, PBC 無任何關聯、背書或官方支援關係**。「Claude」與「Claude Code」為 Anthropic 的商標。本專案透過 Claude Code 的公開 [Hooks API](https://docs.anthropic.com/en/docs/claude-code/hooks) 進行整合。

## 授權

[MIT](./LICENSE)

## 致謝

本專案受 Claude Code hook 系統及 [claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery) 專案啟發。
