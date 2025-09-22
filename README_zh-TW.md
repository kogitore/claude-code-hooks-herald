<div align="center">

[English](./README.md) | [繁體中文](./README_zh-TW.md)

**Changelog:** see [CHANGELOG.md](./CHANGELOG.md) · **Design/Notes:** see [/updates](./updates/)

</div>

> 本專案啟發自 [disler/claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery)

# Claude Code Hooks Herald

Herald 為 Claude Code 提供單一入口的掛鉤系統：所有官方事件都導向 `.claude/hooks/herald.py`，統一處理音效播放、Decision API 安全策略與節流邏輯。

## 功能

- 🛡️ **Herald Dispatcher**：單一入口（Notification / Stop / SubagentStop / PreToolUse / PostToolUse / Session）。
- 🧩 **BaseHook 共用框架**：統一驗證、節流、音效播放，讓各 hook 只需託管業務邏輯。
- 🧠 **Decision API**：支援 Allow / Deny / Ask / BlockStop，並可透過 `decision_policy.json` 客製規則。
- 🔔 **音效回饋**：播放本機 `.wav` 檔，不需 API Key 或網路存取。
- ⏱️ **智慧節流**：依事件種類套用可調整的冷卻時間，避免音效轟炸。

## 快速開始

最精簡的啟用步驟如下：

1. **放入音效檔**：把 `.wav` 檔案放進 `.claude/sounds/`。
2. **確認設定**：`.claude/settings.json` 已預設將所有事件指向 `herald.py`。若複製到其他專案，請確保該檔案同步更新。
3. **觸發事件**：Claude Code 會自動呼叫 Herald；也可使用 CLI 測試。

## 設定

### 音效對應

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

### Decision Policy

安全決策由 `.claude/hooks/utils/decision_policy.json` 定義，可在 `pre_tool_use.rules` 加入客製規則，或調整 `post_tool_use`、`stop` 行為，例如：

```json
{
  "pre_tool_use": {
    "rules": [
      {
        "type": "command",
        "action": "deny",
        "pattern": "git\\s+reset\\s+--hard",
        "reason": "執行前請再確認"
      }
    ]
  }
}
```

使用者規則會附加在預設規則之後，預設安全守則仍會生效。

**快速開始：** 將 `.claude/hooks/utils/decision_policy.example.json` 複製為 `decision_policy.json`，刪除不需要的區段後再調整 regex 與 reason。樣板涵蓋常見情境（封鎖 git reset、提示 sudo 安裝、保護憑證檔）且未命中規則時預設允許。完整指引請參考 [updates/decisions/0003-decision-policy-template_zh-TW.md](./updates/decisions/0003-decision-policy-template_zh-TW.md)。

**內建標籤**（可於 `tags` 陣列直接使用）：

- `system:dangerous` → 極高風險指令（`rm -rf /`、`shutdown`、`reboot`），預設嚴重度 `critical`。
- `package:install` → 套件管理工具安裝/更新指令（`npm install`、`pip install`、`uv pip` 等），嚴重度 `medium`。
- `git:destructive` → 可能清除工作區的 Git 指令（`git reset --hard`、`git clean -fd` 等），嚴重度 `high`。
- `secrets:file` → 憑證或敏感設定檔案路徑（`.env`、`id_rsa`、`*.pem` 等），嚴重度 `high`。
- `dependency:lock` → 依賴鎖定檔（`package-lock.json`、`poetry.lock`、`requirements.txt` 等），嚴重度 `medium`。

仍可同時保留自訂 regex，以結合專案特定規則；未知標籤會被忽略不會造成錯誤。

## 音效檔

請在 `.claude/sounds/` 放置下列 `.wav`：

- `task_complete.wav`：Stop 事件播放
- `agent_complete.wav`：SubagentStop 事件播放
- `user_prompt.wav`：Notification 事件播放

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
- 整合測試會檢查 `.claude/settings.json` 是否指向 `herald.py`，並驗證 Decision Policy 的 deny/ask 邏輯。

## 授權

MIT License（詳見 LICENSE）

## 致謝

本專案受 Claude Code hook 系統範例及 [claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery) 專案啟發。

## 輸出與環境變數

- JSON 單一輸出：每個 hook 僅輸出一段 JSON（例如 `{"continue": true}` 或 Decision API 回應）。
- 音效路徑覆寫：以環境變數指定音效資料夾（優先於設定檔）
  - `CLAUDE_SOUNDS_DIR` 或 `AUDIO_SOUNDS_DIR`
  - 範例：

```
export CLAUDE_SOUNDS_DIR="/absolute/path/to/sounds"
```

## 常用指令範例

- Dispatcher 測試（Notification）：

```
echo '{"message": "Hi"}' | uv run .claude/hooks/herald.py --hook Notification --enable-audio
```

- PreToolUse 安全檢查：

```
echo '{"tool": "bash", "toolInput": {"command": "rm -rf /"}}' | uv run .claude/hooks/herald.py --hook PreToolUse
```
