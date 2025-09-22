---
id: 0003
status: accepted
date: 2025-09-18
related: [0001, 0002]
---

> **[English Version](./0003-decision-policy-template.md)**

# 決策：Decision Policy 進階樣板

## 背景
- Herald 已將所有官方事件（Notification、Stop、SubagentStop、Pre/PostToolUse、Session）統一交給 dispatcher。
- 內建規則僅防堵最危險的 `rm -rf /` 與憑證檔編輯，團隊仍需要擴充（如封鎖 `git reset --hard`、提示 `sudo apt install`）。
- 直接手寫 `decision_policy.json` 容易出錯：JSON 無法註解且規則順序具有優先權。

## 考量方案
1. **僅提供說明文件**：README 描述做法，使用者自行組裝 JSON。
2. **提供樣板檔**：在實際政策檔旁放示範 JSON，使用者複製後裁剪。
3. **建立 CLI 精靈**：透過互動式工具產生 JSON。

## 決策
採用方案 2：提供 `.claude/hooks/utils/decision_policy.example.json` 高範例並撰寫雙語文件，教導如何複製、裁剪與擴充。範例靠近實際設定檔以方便查找，README 亦同步加入操作步驟。

## 影響
- **優點**：導入更快速；常見規則（封鎖 git reset、提示 sudo 等）可直接複製；與 README/README_zh-TW 說明一致。
- **取捨**：樣板需隨內建預設更新；JSON 無法註解，但透過 `metadata.notes` 提供指引。

## 實作重點
- 樣板位於 `.claude/hooks/utils/decision_policy.example.json`，內容包含：
  - 指令／路徑執行的 deny / ask 範例。
  - `metadata`、`default`、`post_tool_use`、`stop`、`session` 擴充欄位。
- README 英文／繁中介紹模板與操作流程。
- 測試 `test_decision_api.py::test_custom_policy_extends_rules` 確認自訂規則會疊加於預設規則之上。

## 參考資料
- `.claude/hooks/utils/decision_api.py`
- `.claude/hooks/utils/decision_policy.json`
- `.claude/hooks/tests/test_decision_api.py`
- `README.md`, `README_zh-TW.md`
