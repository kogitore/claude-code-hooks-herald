"""音頻分派器 - 專責處理音頻相關功能

這個模組將音頻處理邏輯從 HeraldDispatcher 中分離出來，
實現單一責任原則，提高代碼的可維護性和可測試性。
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from utils.audio_manager import AudioManager
    from herald import DispatchContext, HandlerResult

from utils.dispatch_types import AudioReport
from utils.common_io import generate_audio_notes


def _default_throttle_key(context: "DispatchContext", audio_type: str) -> str:
    """生成默認節流鍵"""
    content = f"{context.event_type}:{audio_type}:{context.payload}"
    return hashlib.md5(content.encode()).hexdigest()[:8]


class AudioDispatcher:
    """音頻分派器 - 專責處理所有音頻相關功能
    
    職責：
    1. 音頻類型解析和路徑解析
    2. 音頻節流邏輯處理
    3. 音頻播放執行
    4. 音頻上下文管理
    5. 音頻錯誤處理和報告
    """

    def __init__(self, audio_manager: "AudioManager"):
        """初始化音頻分派器
        
        Args:
            audio_manager: AudioManager 實例
        """
        self.audio_manager = audio_manager

    def handle_audio(
        self,
        context: "DispatchContext",
        handler_result: Optional["HandlerResult"] = None,
        enable_audio: bool = False
    ) -> AudioReport:
        """處理音頻分派的主要入口點
        
        Args:
            context: 分派上下文
            handler_result: 處理器結果
            enable_audio: 是否啟用音頻
            
        Returns:
            AudioReport: 音頻處理結果報告
        """
        # 初始化報告
        report = AudioReport()
        
        try:
            # 解析音頻類型
            resolved_audio_type = self._resolve_audio_type(context, handler_result)
            report.resolved_audio_type = resolved_audio_type
            
            # 如果沒有音頻類型或被停止分派，直接返回
            if not resolved_audio_type or context.stop_dispatch:
                return report
            
            # 如果 handler 明確抑制音頻，直接返回
            if handler_result and getattr(handler_result, 'suppress_audio', False):
                report.notes.append("Audio suppressed by handler")
                return report
            
            # 解析節流參數
            throttle_info = self._resolve_throttle_info(context, handler_result, resolved_audio_type)
            report.throttle_key = throttle_info["key"]
            
            # 檢查節流
            throttled = self._check_throttle(throttle_info, resolved_audio_type)
            report.throttled = throttled
            
            # 解析音頻文件路徑
            audio_path = self.audio_manager.resolve_file(resolved_audio_type)
            report.audio_path = audio_path
            
            # 如果未被節流且啟用音頻，執行播放
            if not throttled and enable_audio:
                audio_result = self._play_audio(context, resolved_audio_type, throttle_info["key"])
                report.played = audio_result["played"]
                report.audio_context = audio_result["context"]
                
                # 標記已發送（用於節流）
                if throttle_info["key"] and audio_result["played"]:
                    self.audio_manager.mark_emitted(throttle_info["key"])
            
            # 生成音頻註記
            throttle_window = throttle_info.get("window", 0)
            throttle_msg = f"Throttled (<= {throttle_window}s)" if throttle_window > 0 else "Throttled"
            
            report.notes.extend(
                generate_audio_notes(
                    throttled=report.throttled,
                    path=report.audio_path,
                    played=report.played,
                    enabled=enable_audio,
                    throttle_msg=throttle_msg
                )
            )
            
        except Exception as e:
            report.add_error(f"Audio processing error: {e}")
            # 音頻錯誤不應該破壞整個分派流程
        
        return report

    def _resolve_audio_type(
        self, 
        context: "DispatchContext", 
        handler_result: Optional["HandlerResult"]
    ) -> Optional[str]:
        """解析音頻類型
        
        優先級：HandlerResult > DispatchContext > event_type
        """
        if handler_result and handler_result.audio_type:
            return handler_result.audio_type
        
        if context.audio_type:
            return context.audio_type
            
        # 默認使用事件類型作為音頻類型
        return context.event_type

    def _resolve_throttle_info(
        self,
        context: "DispatchContext",
        handler_result: Optional["HandlerResult"],
        resolved_audio_type: str
    ) -> Dict[str, Any]:
        """解析節流相關信息
        
        Returns:
            Dict: 包含 key, window 等節流信息
        """
        # 解析節流窗口
        throttle_window = 0
        if handler_result and handler_result.throttle_window:
            throttle_window = handler_result.throttle_window
        
        # 解析節流鍵
        throttle_key = None
        if handler_result and handler_result.throttle_key:
            throttle_key = handler_result.throttle_key
        elif context.throttle_key:
            throttle_key = context.throttle_key
        
        # 如果沒有明確的節流鍵，生成默認的
        if not throttle_key and resolved_audio_type:
            throttle_key = _default_throttle_key(context, resolved_audio_type)
        
        return {
            "key": throttle_key,
            "window": int(throttle_window or 0)
        }

    def _check_throttle(self, throttle_info: Dict[str, Any], resolved_audio_type: str) -> bool:
        """檢查是否應該節流
        
        Args:
            throttle_info: 節流信息
            resolved_audio_type: 解析後的音頻類型
            
        Returns:
            bool: True 如果應該節流
        """
        throttle_window = throttle_info["window"]
        throttle_key = throttle_info["key"]
        
        if throttle_window > 0 and throttle_key:
            window = self.audio_manager.get_throttle_window(resolved_audio_type, throttle_window)
            if window > 0:
                return self.audio_manager.should_throttle(throttle_key, window)
        
        return False

    def _play_audio(
        self,
        context: "DispatchContext",
        resolved_audio_type: str,
        throttle_key: Optional[str]
    ) -> Dict[str, Any]:
        """執行音頻播放
        
        Args:
            context: 分派上下文
            resolved_audio_type: 解析後的音頻類型
            throttle_key: 節流鍵
            
        Returns:
            Dict: 播放結果 {"played": bool, "context": dict}
        """
        # Goal 3: Enhanced play_audio with additionalContext
        additional_context = {
            "heraldDispatch": True,
            "originalEventName": context.event_type,
            "resolvedAudioType": resolved_audio_type,
            "throttleKey": throttle_key
        }
        
        played, _, audio_context = self.audio_manager.play_audio(
            resolved_audio_type,
            enabled=True,  # 這裡已經通過了 enable_audio 檢查
            additional_context=additional_context
        )
        
        return {
            "played": played,
            "context": audio_context
        }

    def get_health_status(self) -> Dict[str, Any]:
        """獲取音頻分派器健康狀態
        
        Returns:
            Dict: 健康狀態報告
        """
        try:
            # 檢查 AudioManager 狀態
            audio_manager_health = hasattr(self.audio_manager, 'config') and self.audio_manager.config is not None
            
            return {
                "component": "AudioDispatcher",
                "healthy": audio_manager_health,
                "audio_manager_status": "OK" if audio_manager_health else "ERROR",
                "last_check": "now"
            }
        except Exception as e:
            return {
                "component": "AudioDispatcher", 
                "healthy": False,
                "error": str(e),
                "last_check": "now"
            }