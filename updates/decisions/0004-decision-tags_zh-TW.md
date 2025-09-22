---
id: 0004
status: accepted
date: 2025-09-18
related: [0003]
---

> **[English Version](./0004-decision-tags.md)**

# 決策：標籤式 Decision Policy

## 背景
- 單靠 regex 維護政策成本高：團隊經常重複貼上 `npm install`、`git reset --hard`、機密檔案等複雜正則。
- `decision_policy.example.json` 雖已提供 `tags` 欄位，但執行時未使用；仍得手寫正則。
- 我們希望以語意標籤與嚴重度分級，提升可讀性與可審計性。

## 決策
在 `DecisionAPI` 新增內建標籤庫與嚴重度排序。政策規則可僅寫 `"tags": ["package:install"]`（可選擇額外提供 regex）。每個標籤映射到既定 pattern、預設嚴重度與類型（command/path），決策回傳時會夾帶 severity 與 tags。

## 影響
- **優點**：大幅降低入門門檻；多數常見守門規則可直接用標籤表達。嚴重度 metadata 讓日後儀表板或 middleware 能據此排序。
- **中性**：仍保留 regex 完整支援，可與標籤並存。
- **缺點**：標籤庫需謹慎維護；若未來修改語意需公告以免造成預期外影響。

## 實作重點
- `.claude/hooks/utils/decision_api.py` 新增 `TagMatcher` 與 `_TAG_LIBRARY`（含 `system:dangerous`、`package:install`、`git:destructive`、`secrets:file`、`dependency:lock` 等）。
- `_CompiledRule` 由此儲存 `tags`、`severity`，決策回傳 `additionalContext` 會附帶 `tags` 與 `severity`。
- 更新預設政策、自訂政策與樣板，同步 README/README_zh-TW 說明可用標籤與嚴重度。
- 單元測試 (`test_decision_api.py::test_tag_rule_matches`) 驗證標籤匹配與嚴重度傳遞；與 ADR 0003 相互參照。

## 參考資料
- `.claude/hooks/utils/decision_api.py`
- `.claude/hooks/utils/decision_policy.json`
- `.claude/hooks/utils/decision_policy.example.json`
- `.claude/hooks/tests/test_decision_api.py`
- `README.md`, `README_zh-TW.md`
