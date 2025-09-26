<div align="center">

[English](./README.md) | [繁體中文](./README_zh-TW.md)

**Changelog:** see [CHANGELOG.md](./CHANGELOG.md) · **Design/Notes:** see [/updates](./updates/)

</div>

> 本專案啟發自 [disler/claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery)

# Claude Code Hooks Herald

Herald 為 Claude Code 提供單一入口的掛鉤系統：所有官方事件都導向 `.claude/hooks/herald.py`，統一處理音效播放、Decision API 安全策略與節流邏輯。

## 功能

- 🛡️ **Herald Dispatcher**：單一入口支援 8/9 官方 Claude Code 事件（已實作8個，PreCompact待完成）。
- 🧩 **BaseHook 共用框架**：統一驗證、節流、音效播放，讓各 hook 只需託管業務邏輯。
- 🧠 **Decision API**：支援 Allow / Deny / Ask / BlockStop，並可透過 `decision_policy.json` 客製規則。
- 🔔 **音效回饋**：播放本機 `.wav` 檔，不需 API Key 或網路存取。
- ⏱️ **智慧節流**：依事件種類套用可調整的冷卻時間，避免音效轟炸。
- ✅ **Claude Code 相容**：完整支援新舊兩種欄位格式（`tool_name`/`tool_input` 與 legacy 格式）。

## 快速開始

### 系統需求

**基本需求：**
- **Claude Code CLI** - [安裝 Claude Code](https://claude.ai/code) (本 hooks 系統與 Claude Code 整合)
- **Python 3.9+** (已測試 Python 3.11-3.13)
- **uv** (超快速 Python 套件管理器) - [安裝 uv](https://docs.astral.sh/uv/getting-started/installation/)
- **Git** (用於複製儲存庫)
- **音效系統：**
  - **macOS:** `afplay` (內建)
  - **Linux:** `ffplay` (ffmpeg 套件) 或 `aplay` (alsa-utils)
  - **Windows:** `winsound` (Python 內建)

**安裝 uv (如尚未安裝)：**
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 替代方案: pipx install uv
```

### 設置步驟

1. **複製並進入目錄：**
   ```bash
   git clone <repository-url>
   cd claude-code-hooks-herald
   ```

2. **放入音效檔：** 將 `.wav` 檔案放進 `.claude/sounds/`：
   ```bash
   # 必要的音效檔案：
   # - task_complete.wav (Stop 事件用)
   # - agent_complete.wav (SubagentStop 事件用)
   # - user_prompt.wav (Notification 事件用)
   ```

3. **確認設定：** `.claude/settings.json` 已預設將所有事件導向 `herald.py`。複製到你的 Claude 專案：
   ```bash
   cp .claude/settings.json /path/to/your/claude/project/.claude/
   ```

4. **設定執行權限：**
   ```bash
   chmod +x .claude/hooks/*.py
   ```

5. **測試安裝：**
   ```bash
   # 測試 herald 系統
   echo '{"message": "test"}' | uv run .claude/hooks/herald.py --hook Notification --enable-audio

   # 測試安全政策
   echo '{"tool": "bash", "toolInput": {"command": "rm -rf /"}}' | uv run .claude/hooks/herald.py --hook PreToolUse
   ```

### 驗證

**預期輸出：**
- Notification 測試: `{"continue": true}` + 音效播放
- 安全測試: `{"continue": false, "permissionDecision": "deny"}` (危險指令被阻擋)

**疑難排解：**
- **無音效：**
  - 檢查 `.claude/sounds/` 目錄存在且有 `.wav` 檔案
  - Linux: 安裝音效相依性: `sudo apt-get install ffmpeg` 或 `sudo apt-get install alsa-utils`
- **權限錯誤：** 執行 `chmod +x .claude/hooks/*.py`
- **Python/uv 找不到：** 確保兩者都在你的 `$PATH` 中
- **Claude Code 偵測不到 hooks：** 驗證 `.claude/settings.json` 在專案根目錄
- **"找不到模組" 錯誤：** 從儲存庫根目錄執行

**平台特定注意事項：**
- **Windows：** 某些防毒軟體可能標記 Python 腳本 - 將專案目錄加入排除清單
- **Linux/WSL：** 確保音效驅動程式正確配置以進行音效播放
- **macOS：** 如有提示，請授予 Terminal/Claude Code 麥克風/音效權限

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
