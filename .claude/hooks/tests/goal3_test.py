#!/usr/bin/env python3
"""
Goal 3 測試 Hook - 專門用於測試非阻塞音效播放和 additionalContext 功能
"""

import argparse
import json
import sys
from pathlib import Path

# 添加 utils 到路徑
sys.path.insert(0, str(Path(__file__).parent / "utils"))

from utils.base_hook import BaseHook, HookExecutionResult
from utils.common_io import parse_stdin


class Goal3TestHook(BaseHook):
    """Goal 3 測試 Hook - 展示非阻塞音效和結構化通信"""
    
    default_audio_event = "Stop"
    default_throttle_seconds = 0  # 不節流以便測試
    
    def validate_input(self, data):
        return True
        
    def is_applicable(self, data):
        return True
        
    def process(self, data):
        # Goal 3: 在 additionalContext 中返回結構化數據
        return {
            "goal3Features": {
                "nonBlockingAudio": True,
                "structuredCommunication": True,
                "additionalContextSupport": True
            },
            "processedData": data
        }
        
    def handle_error(self, error):
        return {"error": str(error)}
    
    def execute(self, data, *, enable_audio=False, **kwargs):
        """Override execute to add custom additionalContext"""
        result = super().execute(data, enable_audio=enable_audio, **kwargs)
        
        # Goal 3: 添加自定義結構化上下文
        result.additional_context.update({
            "goal3Test": True,
            "hookName": "Goal3TestHook",
            "features": {
                "audioPerformance": f"{result.audio_played}",
                "contextStructure": "enhanced",
                "communicationStandard": "additionalContext"
            }
        })
        
        return result


def main():
    parser = argparse.ArgumentParser(description="Goal 3 測試 Hook")
    parser.add_argument("--enable-audio", action="store_true", help="啟用音效播放")
    parser.add_argument("--json-only", action="store_true", help="僅輸出 JSON")
    args = parser.parse_args()
    
    payload, _ = parse_stdin()
    
    hook = Goal3TestHook()
    result = hook.execute(payload, enable_audio=args.enable_audio)
    
    # 輸出遙測到 stderr
    if not args.json_only:
        try:
            print(
                f"[Goal3Test] audioPlayed={result.audio_played} "
                f"throttled={result.throttled} "
                f"audioContext={bool(result.audio_context)} "
                f"additionalContext={bool(result.additional_context)}",
                file=sys.stderr
            )
        except Exception:
            pass
    
    # 輸出結構化回應
    hook.emit_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())