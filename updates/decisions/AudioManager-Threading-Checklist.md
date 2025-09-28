# AudioManager 線程安全優化 - 實作檢查清單

## 🎯 優化目標
- 添加完整線程安全機制
- 保護文件 I/O 操作和共享狀態
- 維持 <100ms hook 執行性能
- 保持向後兼容性

## 📋 實作步驟清單

### Phase 3.1: 核心線程基礎設施 (高優先級)

#### ✅ Step 1: 環境準備
- [ ] `cp utils/audio_manager.py utils/audio_manager.py.backup`
- [ ] 確認當前音效功能正常: `uv run herald.py --hook Notification --enable-audio`
- [ ] 記錄基準性能: 測量當前 `play_audio()` 執行時間

#### ✅ Step 2: 添加線程鎖基礎設施
**在 `AudioManager.__init__()` 開頭添加：**
```python
import threading
from threading import RLock, Lock
from contextlib import contextmanager

class AudioManager:
    def __init__(self):
        # 線程安全鎖 - 添加在初始化最開始
        self._config_lock = RLock()      # 配置訪問鎖 (可重入)
        self._throttle_lock = Lock()     # 節流檔案操作鎖
        self._playback_lock = RLock()    # 音效播放協調鎖 (可重入)

        # 原有初始化程式碼用 config_lock 保護
        with self._config_lock:
            # ... 現有的初始化程式碼 (line 132 onwards)
```

#### ✅ Step 3: 實作線程安全的節流檔案操作
**替換 `_read_throttle()` 和 `_write_throttle()` 方法：**

```python
def _read_throttle_safe(self) -> Dict[str, float]:
    """線程安全的節流數據讀取，包含檔案鎖定."""
    with self._throttle_lock:
        try:
            if not self._throttle_path.exists():
                return {}

            # 跨平台檔案鎖定實作
            if self._use_file_locking():
                return self._read_with_file_lock(self._throttle_path)
            else:
                # 降級到無鎖定模式
                with open(self._throttle_path, 'r') as f:
                    return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

def _write_throttle_safe(self, data: Dict[str, float]) -> None:
    """線程安全的節流數據寫入，包含檔案鎖定."""
    with self._throttle_lock:
        try:
            self._throttle_path.parent.mkdir(parents=True, exist_ok=True)

            if self._use_file_locking():
                self._write_with_file_lock(self._throttle_path, data)
            else:
                # 降級到無鎖定模式
                with open(self._throttle_path, 'w') as f:
                    json.dump(data, f, indent=2)
        except OSError:
            pass  # 靜默失敗，保持向後兼容性

def _use_file_locking(self) -> bool:
    """檢查是否可以使用檔案鎖定."""
    try:
        import fcntl  # Unix 系統
        return True
    except ImportError:
        try:
            import msvcrt  # Windows 系統
            return True
        except ImportError:
            return False
```

#### ✅ Step 4: 跨平台檔案鎖定實作
**添加檔案鎖定輔助方法：**

```python
def _read_with_file_lock(self, file_path: Path) -> Dict[str, float]:
    """使用檔案鎖定讀取數據."""
    import platform

    if platform.system() == "Windows":
        return self._read_windows_locked(file_path)
    else:
        return self._read_unix_locked(file_path)

def _read_unix_locked(self, file_path: Path) -> Dict[str, float]:
    """Unix 系統檔案鎖定讀取."""
    import fcntl

    with open(file_path, 'r') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # 共享鎖
        try:
            data = json.load(f)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # 解鎖
        return data

def _read_windows_locked(self, file_path: Path) -> Dict[str, float]:
    """Windows 系統檔案鎖定讀取."""
    import msvcrt

    with open(file_path, 'r') as f:
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
            data = json.load(f)
        finally:
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        return data

def _write_with_file_lock(self, file_path: Path, data: Dict[str, float]) -> None:
    """使用檔案鎖定寫入數據."""
    import platform

    if platform.system() == "Windows":
        self._write_windows_locked(file_path, data)
    else:
        self._write_unix_locked(file_path, data)

def _write_unix_locked(self, file_path: Path, data: Dict[str, float]) -> None:
    """Unix 系統檔案鎖定寫入."""
    import fcntl

    with open(file_path, 'w') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 獨占鎖
        try:
            json.dump(data, f, indent=2)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # 解鎖

def _write_windows_locked(self, file_path: Path, data: Dict[str, float]) -> None:
    """Windows 系統檔案鎖定寫入."""
    import msvcrt

    with open(file_path, 'w') as f:
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
            json.dump(data, f, indent=2)
        finally:
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
```

### Phase 3.2: 並發音效播放 (中優先級)

#### ✅ Step 5: 線程安全的音效播放
**替換現有的 `play_audio()` 方法：**

```python
def play_audio_safe(self, audio_type: str, enabled: bool = False,
                   additional_context: Optional[Dict[str, Any]] = None) -> tuple[bool, Optional[Path], Dict[str, Any]]:
    """線程安全的音效播放，支援並發請求處理."""

    # 使用播放鎖保護整個播放流程
    with self._playback_lock:
        # 線程安全的配置訪問
        with self._config_lock:
            audio_type = self._normalize_key(audio_type)
            path = self.resolve_file(audio_type)

        # 建立播放上下文 (線程安全)
        context = {
            "audioType": audio_type,
            "enabled": enabled,
            "playerCmd": self._player_cmd,
            "volume": self.volume,
            "filePath": str(path) if path else None,
            **(additional_context or {})
        }

        if not enabled or path is None:
            context["status"] = "skipped"
            context["reason"] = "disabled" if not enabled else "file_not_found"
            return False, path, context

        # 線程安全的播放執行
        return self._execute_playback_safe(path, context)

def _execute_playback_safe(self, path: Path, context: Dict[str, Any]) -> tuple[bool, Path, Dict[str, Any]]:
    """執行音效播放，保證線程安全."""
    try:
        # 音效播放已經是異步和線程安全的
        if self._player_cmd == "winsound":
            rc = _play_with_windows(str(path), volume=self.volume, timeout_s=self._timeout_s)
        else:
            rc = _play_with(self._player_cmd, self._player_base_args + [str(path)], timeout_s=self._timeout_s)

        success = (rc == 0)
        context.update({
            "status": "played" if success else "failed",
            "returnCode": rc
        })
        return success, path, context

    except Exception as e:
        context.update({
            "status": "failed",
            "error": str(e)
        })
        return False, path, context

# 保持向後兼容性 - 原方法調用新的安全方法
def play_audio(self, audio_type: str, enabled: bool = False,
               additional_context: Optional[Dict[str, Any]] = None) -> tuple[bool, Optional[Path], Dict[str, Any]]:
    """向後兼容的音效播放方法."""
    return self.play_audio_safe(audio_type, enabled, additional_context)
```

#### ✅ Step 6: 線程安全的節流檢查
**更新 `is_throttled()` 方法：**

```python
def is_throttled_safe(self, audio_type: str, throttle_window_seconds: int) -> bool:
    """線程安全的節流檢查."""
    if throttle_window_seconds <= 0:
        return False

    audio_type = self._normalize_key(audio_type)
    now = time.time()

    # 線程安全的節流數據訪問
    throttle_data = self._read_throttle_safe()
    last_played = throttle_data.get(audio_type, 0.0)

    if now - last_played < throttle_window_seconds:
        return True

    # 線程安全更新節流數據
    throttle_data[audio_type] = now
    self._write_throttle_safe(throttle_data)
    return False

# 保持向後兼容性
def is_throttled(self, audio_type: str, throttle_window_seconds: int) -> bool:
    """向後兼容的節流檢查."""
    return self.is_throttled_safe(audio_type, throttle_window_seconds)
```

### Phase 3.3: 配置線程安全 (低優先級)

#### ✅ Step 7: 線程安全的配置訪問
**添加配置安全方法：**

```python
def get_config_safe(self, key: str, default: Any = None) -> Any:
    """線程安全的配置訪問."""
    with self._config_lock:
        return self._config_manager.get(key, default)

def reload_config_safe(self) -> None:
    """線程安全的配置重載."""
    with self._config_lock:
        self._config_manager.clear_cache()

        # 重新載入配置
        cfg = _load_config(self._config_manager)

        # 更新映射和音量設定
        if "sound_files" in cfg:
            mappings = cfg["sound_files"].get("mappings", {})
            for raw_key, value in mappings.items():
                canonical = _canonical_audio_key(raw_key)
                self.config.mappings[canonical] = str(value)

        if "audio_settings" in cfg:
            volume = cfg["audio_settings"].get("volume")
            if isinstance(volume, (int, float)):
                self.volume = max(0.0, min(1.0, float(volume)))
```

### Phase 3.4: 性能監控和測試 (高優先級)

#### ✅ Step 8: 添加性能監控
**添加性能監控工具：**

```python
import time
from contextlib import contextmanager

@contextmanager
def _performance_monitor(self, operation_name: str, warn_threshold_ms: float = 10.0):
    """監控操作性能，檢查線程鎖定開銷."""
    start = time.time()
    try:
        yield
    finally:
        duration = (time.time() - start) * 1000
        if duration > warn_threshold_ms:
            # 可選：記錄慢操作（用於調試）
            pass

# 在關鍵方法中使用監控
def play_audio_safe(self, audio_type: str, enabled: bool = False, additional_context: Optional[Dict[str, Any]] = None):
    with self._performance_monitor("play_audio_safe"):
        # ... 現有的播放邏輯
```

#### ✅ Step 9: 基本功能測試
**創建測試腳本 `test_audio_threading.py`：**

```python
#!/usr/bin/env python3
"""AudioManager 線程安全測試"""

import threading
import time
import sys
from pathlib import Path

# 添加當前目錄到路徑
sys.path.insert(0, str(Path(__file__).parent))
from utils.audio_manager import AudioManager

def test_concurrent_playback():
    """測試並發音效播放."""
    print("🧪 測試並發音效播放...")

    audio_manager = AudioManager()
    results = []

    def play_audio_worker(worker_id: int):
        result = audio_manager.play_audio_safe("notification", enabled=True)
        results.append((worker_id, result[0]))  # (worker_id, success)

    # 啟動 5 個並發線程
    threads = []
    for i in range(5):
        t = threading.Thread(target=play_audio_worker, args=(i,))
        threads.append(t)
        t.start()

    # 等待完成
    for t in threads:
        t.join()

    print(f"   完成 {len(results)} 個並發播放請求")
    return len(results) == 5

def test_throttle_thread_safety():
    """測試節流的線程安全性."""
    print("🧪 測試節流線程安全...")

    audio_manager = AudioManager()
    throttle_results = []

    def check_throttle_worker():
        # 使用 1 秒節流窗口
        is_throttled = audio_manager.is_throttled_safe("test_audio", 1)
        throttle_results.append(is_throttled)

    # 啟動 10 個並發節流檢查
    threads = []
    for i in range(10):
        t = threading.Thread(target=check_throttle_worker)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # 第一個請求應該不被節流，後續請求應該被節流
    non_throttled_count = len([r for r in throttle_results if not r])
    print(f"   非節流請求數: {non_throttled_count}/10")
    return non_throttled_count == 1

def test_performance_impact():
    """測試性能影響."""
    print("🧪 測試性能影響...")

    audio_manager = AudioManager()

    # 測試播放性能
    times = []
    for i in range(10):
        start = time.time()
        audio_manager.play_audio_safe("notification", enabled=False)  # 不實際播放
        duration = (time.time() - start) * 1000
        times.append(duration)

    avg_time = sum(times) / len(times)
    max_time = max(times)

    print(f"   平均執行時間: {avg_time:.2f}ms")
    print(f"   最大執行時間: {max_time:.2f}ms")

    # 性能目標：平均 < 5ms，最大 < 20ms
    return avg_time < 5.0 and max_time < 20.0

def main():
    print("🚀 AudioManager 線程安全測試")

    tests = [
        ("並發播放", test_concurrent_playback),
        ("節流安全", test_throttle_thread_safety),
        ("性能影響", test_performance_impact),
    ]

    passed = 0
    for test_name, test_func in tests:
        try:
            if test_func():
                print(f"   ✅ {test_name}: 通過")
                passed += 1
            else:
                print(f"   ❌ {test_name}: 失敗")
        except Exception as e:
            print(f"   ❌ {test_name}: 異常 - {e}")

    print(f"\n📊 測試結果: {passed}/{len(tests)} 通過")
    return passed == len(tests)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
```

## 🔍 驗證檢查點

### 基本功能驗證
- [ ] **匯入測試**: `uv run python -c "from utils.audio_manager import AudioManager; AudioManager()"`
- [ ] **播放測試**: `uv run herald.py --hook Notification --enable-audio`
- [ ] **節流測試**: 快速執行同一 hook 兩次，檢查節流效果

### 線程安全驗證
- [ ] **並發測試**: `uv run python test_audio_threading.py`
- [ ] **壓力測試**: 同時執行多個 Herald hook
- [ ] **檔案鎖測試**: 檢查節流檔案在並發訪問下的完整性

### 性能驗證
- [ ] **播放延遲**: 音效播放延遲 < 100ms
- [ ] **鎖定開銷**: 線程鎖定開銷 < 5ms
- [ ] **記憶體使用**: 無明顯記憶體洩漏

### 兼容性驗證
- [ ] **向後兼容**: 原有 `play_audio()` 方法正常工作
- [ ] **Herald 整合**: 所有 hook 正常執行
- [ ] **跨平台**: macOS/Linux/Windows 都能正常工作

## 🚨 常見問題和解決方案

### 問題 1: 檔案鎖定失敗
**症狀**: `fcntl` 或 `msvcrt` 模組不可用
**解決**: 自動降級到無鎖定模式，記錄警告

### 問題 2: 死鎖
**症狀**: 程式掛起或響應緩慢
**解決**: 確保鎖定順序一致，使用 RLock 避免重入問題

### 問題 3: 性能下降
**症狀**: hook 執行時間超過 100ms
**解決**: 檢查鎖定粒度，避免不必要的鎖定

### 問題 4: 並發音效混亂
**症狀**: 多個音效同時播放造成混響
**解決**: 使用播放鎖序列化音效播放，或允許並發但記錄狀態

## 📊 成功標準

**必須達成 (MUST):**
- [ ] 所有現有功能保持正常
- [ ] 無線程安全相關的錯誤
- [ ] Hook 執行時間 < 100ms
- [ ] 跨平台兼容性維持

**期望達成 (SHOULD):**
- [ ] 並發音效播放正常工作
- [ ] 節流機制線程安全
- [ ] 性能影響最小化
- [ ] 檔案操作原子性

**額外收穫 (COULD):**
- [ ] 性能監控和調試工具
- [ ] 更好的錯誤處理
- [ ] 配置熱重載功能

---

**實作者注意事項:**
1. 先完成基礎設施，再處理具體功能
2. 每個 Phase 完成後測試基本功能
3. 注意 RLock vs Lock 的使用場景
4. 保持向後兼容性是最高優先級
5. 檔案鎖定失敗時要有降級方案

*生成時間: 2025-09-24 - Herald System Phase 3 優化*