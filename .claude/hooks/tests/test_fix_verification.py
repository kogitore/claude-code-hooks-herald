#!/usr/bin/env python3
"""
驗證 ConfigManager 修復的測試腳本
按照 Claude 建議的測試步驟
"""

import sys
import os
import threading

# 添加當前目錄到Python路徑
sys.path.insert(0, os.path.dirname(__file__))

from utils.config_manager import ConfigManager

def test_basic_functionality():
    """步驟 1: 基本功能測試"""
    print("🧪 開始基本功能測試...")
    
    # 測試基本實例化
    manager = ConfigManager.get_instance(['test_path'])
    print("✓ 基本實例化成功")
    
    # 測試 singleton 行為
    manager2 = ConfigManager.get_instance()
    assert manager is manager2, "Singleton 行為失敗"
    print("✓ Singleton 行為正確")
    
    # 測試search_paths設置
    manager3 = ConfigManager.get_instance(['new_path'])
    assert manager3 is manager, "應該是同一個實例"
    assert manager3.search_paths == ['new_path'], "search_paths應該被更新"
    print("✓ search_paths 更新正確")

def test_concurrent_access():
    """步驟 2: 並發測試"""
    print("\n🧪 開始並發安全測試...")
    
    def test_concurrent():
        return ConfigManager.get_instance()
    
    # 並發測試
    results = []
    threads = [threading.Thread(target=lambda: results.append(test_concurrent()))
               for _ in range(10)]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert all(r is results[0] for r in results), "並發測試失敗：獲得了不同的實例"
    print("✓ 並發安全測試通過")

def test_no_infinite_loop():
    """測試無無限循環"""
    print("\n🧪 測試無無限循環...")
    
    import time
    import signal
    
    def timeout_handler(signum, frame):
        raise TimeoutError("測試超時，可能存在無限循環")
    
    # 設置5秒超時
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(5)
    
    try:
        # 多次快速創建實例
        for i in range(100):
            manager = ConfigManager.get_instance([f'path_{i}'])
            if i == 0:
                first_instance = manager
            else:
                assert manager is first_instance, f"第{i}次獲取了不同的實例"
        signal.alarm(0)  # 取消超時
        print("✓ 無無限循環，快速創建100個實例成功")
    except TimeoutError:
        signal.alarm(0)
        raise AssertionError("檢測到無限循環或死鎖")

def test_initialization_state():
    """測試初始化狀態"""
    print("\n🧪 測試初始化狀態...")
    
    manager = ConfigManager.get_instance()
    
    # 檢查實例變量
    assert hasattr(manager, '_initialized'), "應該有_initialized屬性"
    assert manager._initialized == True, "_initialized應該為True"
    assert hasattr(manager, 'search_paths'), "應該有search_paths屬性"
    assert hasattr(manager, '_config_cache'), "應該有_config_cache屬性"
    assert hasattr(manager, '_file_lock'), "應該有_file_lock屬性"
    
    print("✓ 初始化狀態正確")

def main():
    """主測試函數"""
    print("🔧 ConfigManager 修復驗證測試\n")
    
    try:
        test_basic_functionality()
        test_concurrent_access()
        test_no_infinite_loop()
        test_initialization_state()
        
        print("\n🎉 所有測試通過！ConfigManager 修復成功")
        print("✅ 修復無限循環 - 簡化 singleton 邏輯")
        print("✅ 保持向後兼容 - ConfigManager.get_instance() 接口不變")
        print("✅ 線程安全 - 避免死鎖問題")
        print("✅ 通過測試 - 確保功能正常運行")
        
    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()