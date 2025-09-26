> **[English Version](./windows-volume-control.md)**

# 實驗：Windows 音量控制

## 假設
僅使用 Python 標準函式庫即可在 Windows 上實現逐 Hook 的音量控制，且不影響系統整體音量，也不引入第三方依賴。

## 設定
- 平台：Windows 11 (22H2)
- Python：3.11，僅使用標準函式庫
- 測試音效：儲存在 `.claude/sounds/` 內的 2–3 秒 WAV 範例
- 環境變數：不設定 `AUDIO_PLAYER_CMD`，確保真實播放

## 步驟
1. 評估第三方函式庫（`pygame`、`pydub`、`sounddevice`）對音量控制的支援程度。
2. 測試透過 `ctypes` 呼叫 Windows Core Audio API 的可行性。
3. 嘗試預先產生不同音量的 WAV 檔（離線增益）。
4. 使用 `audioop` + `wave` + `io` 在記憶體內調整音量，再透過 `winsound.PlaySound(..., SND_MEMORY)` 播放。
5. 量測延遲並驗證異常時的回退流程。

## 結果
- ✅ 音量 0.2、0.5、1.0 皆呈現明顯差異。
- ✅ 短音效處理時間 < 50 ms，且無臨時檔案。
- ✅ 異常處理：WAV 損毀時會回退至原始播放。
- ❌ 僅支援 WAV 格式；大型檔案會佔用更多記憶體。

## 分析
記憶體內處理符合零依賴與低延遲需求。雖然 CPU 與記憶體消耗會隨檔案大小增加，但 Hook 音效普遍很短，可接受此權衡。

## 後續
- 追蹤長時間播放的記憶體使用狀況。
- 若未來需要播放非 WAV 格式，評估外部播放器選項。
- 補充 `winsound` 無法播放時的疑難排解指南（例如多媒體服務未啟動）。
