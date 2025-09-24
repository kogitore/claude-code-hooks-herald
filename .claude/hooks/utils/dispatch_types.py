"""共用類型定義用於 Herald Dispatcher 重構

這個模組定義了重構過程中各組件共用的類型和數據結構。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class AudioReport:
    """音頻處理結果報告"""
    
    played: bool = False
    throttled: bool = False
    audio_path: Optional[Path] = None
    audio_context: Dict[str, Any] = field(default_factory=dict)
    throttle_key: Optional[str] = None
    resolved_audio_type: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def add_error(self, error: str) -> None:
        """添加錯誤到報告"""
        self.errors.append(error)

    def add_note(self, note: str) -> None:
        """添加註記到報告"""
        self.notes.append(note)

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式用於報告"""
        return {
            "played": self.played,
            "throttled": self.throttled,
            "audio_path": str(self.audio_path) if self.audio_path else None,
            "audio_context": self.audio_context,
            "throttle_key": self.throttle_key,
            "resolved_audio_type": self.resolved_audio_type,
            "notes": self.notes,
            "errors": self.errors
        }


@dataclass 
class DispatchRequest:
    """分派請求的封裝"""
    
    event_type: str
    payload: Dict[str, Any]
    enable_audio: bool = False
    marker: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComponentHealth:
    """組件健康狀態"""
    
    component_name: str
    is_healthy: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    last_check: Optional[str] = None
    
    def add_error(self, error: str) -> None:
        """添加錯誤"""
        self.errors.append(error)
        self.is_healthy = False
    
    def add_warning(self, warning: str) -> None:
        """添加警告"""
        self.warnings.append(warning)