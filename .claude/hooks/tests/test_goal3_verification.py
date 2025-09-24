#!/usr/bin/env python3
"""
Goal 3 實現驗證測試
測試非阻塞音效播放和結構化通信（additionalContext）
"""

import json
import subprocess
import sys
import time
from pathlib import Path


def test_non_blocking_audio():
    """測試非阻塞音效播放 - 執行時間應 < 100ms"""
    print("🧪 測試非阻塞音效播放...")
    
    from utils.audio_manager import AudioManager
    
    am = AudioManager()
    start_time = time.time()
    
    # 測試非阻塞播放
    played, path, context = am.play_audio("stop", enabled=True)
    
    end_time = time.time()
    elapsed_ms = (end_time - start_time) * 1000
    
    print(f"   執行時間: {elapsed_ms:.2f}ms")
    print(f"   播放結果: {played}")
    print(f"   音效路徑: {path}")
    print(f"   上下文鍵: {list(context.keys())}")
    
    if elapsed_ms < 100:
        print("   ✅ 非阻塞音效播放: 執行時間 < 100ms")
        return True
    else:
        print("   ❌ 非阻塞音效播放: 執行時間過長")
        return False


def test_structured_communication():
    """測試結構化通信 - additionalContext 支援"""
    print("\\n🧪 測試結構化通信（additionalContext）...")
    
    # 使用 Goal3TestHook 測試
    result = subprocess.run(
        ['python3', 'goal3_test.py', '--enable-audio'],
        input='{"testType": "structuredCommunication"}',
        text=True,
        capture_output=True,
        timeout=10
    )
    
    print(f"   返回碼: {result.returncode}")
    
    if result.returncode != 0:
        print(f"   ❌ Hook 執行失敗: {result.stderr}")
        return False
    
    try:
        response = json.loads(result.stdout)
        print(f"   回應鍵: {list(response.keys())}")
        
        # 檢查 additionalContext
        if 'additionalContext' not in response:
            print("   ❌ 缺少 additionalContext")
            return False
        
        ac = response['additionalContext']
        required_keys = ['goal3Test', 'hookName', 'features']
        missing_keys = [k for k in required_keys if k not in ac]
        
        if missing_keys:
            print(f"   ❌ additionalContext 缺少鍵: {missing_keys}")
            return False
        
        # 檢查 audioContext
        if 'audioContext' not in ac:
            print("   ❌ 缺少 audioContext")
            return False
        
        audio_ctx = ac['audioContext']
        audio_required = ['audioType', 'enabled', 'status', 'hookType']
        audio_missing = [k for k in audio_required if k not in audio_ctx]
        
        if audio_missing:
            print(f"   ❌ audioContext 缺少鍵: {audio_missing}")
            return False
        
        print("   ✅ additionalContext 結構正確")
        print(f"   ✅ audioContext 狀態: {audio_ctx['status']}")
        print(f"   ✅ Hook 類型: {audio_ctx['hookType']}")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"   ❌ JSON 解析錯誤: {e}")
        return False


def test_hook_compatibility():
    """測試現有 Hook 的向後兼容性"""
    print("\\n🧪 測試現有 Hook 向後兼容性...")
    
    hooks_to_test = ['stop.py', 'notification.py', 'subagent_stop.py']
    results = []
    
    for hook in hooks_to_test:
        try:
            result = subprocess.run(
                ['python3', hook, '--enable-audio'],
                input='{}',
                text=True,
                capture_output=True,
                timeout=5
            )
            
            if result.returncode == 0:
                try:
                    response = json.loads(result.stdout)
                    if response.get('continue') == True:
                        print(f"   ✅ {hook}: 基本功能正常")
                        results.append(True)
                    else:
                        print(f"   ❌ {hook}: continue != True")
                        results.append(False)
                except json.JSONDecodeError:
                    print(f"   ❌ {hook}: JSON 解析錯誤")
                    results.append(False)
            else:
                print(f"   ❌ {hook}: 執行失敗 (code {result.returncode})")
                results.append(False)
                
        except subprocess.TimeoutExpired:
            print(f"   ❌ {hook}: 執行超時")
            results.append(False)
        except Exception as e:
            print(f"   ❌ {hook}: 異常 {e}")
            results.append(False)
    
    return all(results)


def test_performance_benchmark():
    """測試性能基準 - Goal 3 要求"""
    print("\\n🧪 測試性能基準...")
    
    from utils.audio_manager import AudioManager
    
    am = AudioManager()
    times = []
    
    # 進行 10 次測試
    for i in range(10):
        start = time.time()
        am.play_audio("stop", enabled=True)
        end = time.time()
        times.append((end - start) * 1000)
    
    avg_time = sum(times) / len(times)
    max_time = max(times)
    min_time = min(times)
    
    print(f"   平均執行時間: {avg_time:.2f}ms")
    print(f"   最大執行時間: {max_time:.2f}ms") 
    print(f"   最小執行時間: {min_time:.2f}ms")
    
    if max_time < 100:
        print("   ✅ 性能基準: 所有測試 < 100ms")
        return True
    else:
        print("   ❌ 性能基準: 某些測試 >= 100ms")
        return False


def main():
    """主測試函數"""
    print("🎯 Goal 3: 性能優化和最佳實踐驗證測試\\n")
    
    # 確保在正確的目錄
    hooks_dir = Path(__file__).parent
    original_cwd = Path.cwd()
    
    try:
        import os
        os.chdir(hooks_dir)
        
        tests = [
            ("非阻塞音效播放", test_non_blocking_audio),
            ("結構化通信", test_structured_communication), 
            ("向後兼容性", test_hook_compatibility),
            ("性能基準", test_performance_benchmark)
        ]
        
        results = []
        for test_name, test_func in tests:
            try:
                result = test_func()
                results.append((test_name, result))
            except Exception as e:
                print(f"   ❌ {test_name}: 測試異常 {e}")
                results.append((test_name, False))
        
        # 總結
        print("\\n📊 Goal 3 實現總結:")
        print("=" * 50)
        
        passed = 0
        for test_name, result in results:
            status = "✅ 通過" if result else "❌ 失敗"
            print(f"  {test_name}: {status}")
            if result:
                passed += 1
        
        print(f"\\n總體結果: {passed}/{len(results)} 測試通過")
        
        if passed == len(results):
            print("\\n🎉 Goal 3 完全實現！")
            print("✅ 非阻塞音效播放 - hooks 在 100ms 內執行")
            print("✅ 結構化通信 - 使用 additionalContext 傳遞數據")
            print("✅ 向後兼容性 - 現有 hooks 正常工作")
            print("✅ 性能要求 - 符合官方指導建議")
        else:
            print(f"\\n⚠️  Goal 3 部分實現: {passed}/{len(results)} 測試通過")
            
        return 0 if passed == len(results) else 1
            
    finally:
        os.chdir(original_cwd)


if __name__ == "__main__":
    raise SystemExit(main())