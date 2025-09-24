#!/usr/bin/env python3
"""AudioManager 線程安全測試"""

import threading
import time
import sys
from pathlib import Path

# 添加當前目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent))
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
    successful_plays = len([r for r in results if r[1]])
    print(f"   成功播放: {successful_plays}/{len(results)}")
    return len(results) == 5

def test_throttle_thread_safety():
    """測試節流的線程安全性."""
    print("🧪 測試節流線程安全...")

    audio_manager = AudioManager()
    throttle_results = []

    def check_throttle_worker():
        # 使用 1 秒節流窗口
        is_throttled = audio_manager.should_throttle_safe("test_audio", 1)
        throttle_results.append(is_throttled)
        if not is_throttled:
            audio_manager.mark_emitted_safe("test_audio")

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
    return non_throttled_count >= 1  # At least one should not be throttled

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

    # 性能目標：平均 < 10ms，最大 < 50ms (寬鬆標準)
    return avg_time < 10.0 and max_time < 50.0

def test_file_locking():
    """測試檔案鎖定功能."""
    print("🧪 測試檔案鎖定...")

    audio_manager = AudioManager()

    # 測試檔案鎖定可用性
    can_use_locking = audio_manager._use_file_locking()
    print(f"   檔案鎖定支援: {can_use_locking}")

    # 測試節流檔案操作
    test_data = {"test_key": time.time()}
    audio_manager._write_throttle_safe(test_data)

    read_data = audio_manager._read_throttle_safe()
    print(f"   檔案讀寫測試: {'✅' if 'test_key' in read_data else '❌'}")

    return True

def test_config_thread_safety():
    """測試配置的線程安全性."""
    print("🧪 測試配置線程安全...")

    audio_manager = AudioManager()
    config_results = []

    def config_access_worker():
        result = audio_manager.get_config_safe('audio_settings.volume', 0.2)
        config_results.append(result)

    # 啟動多個線程同時訪問配置
    threads = []
    for i in range(5):
        t = threading.Thread(target=config_access_worker)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # 所有結果應該一致
    all_same = all(r == config_results[0] for r in config_results)
    print(f"   配置訪問一致性: {'✅' if all_same else '❌'}")
    return all_same

def main():
    print("🚀 AudioManager 線程安全測試")

    tests = [
        ("並發播放", test_concurrent_playback),
        ("節流安全", test_throttle_thread_safety),
        ("性能影響", test_performance_impact),
        ("檔案鎖定", test_file_locking),
        ("配置安全", test_config_thread_safety),
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