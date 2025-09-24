"""處理器註冊管理器 - 專責管理所有 Handler 和 Middleware

這個模組將處理器和中間件的註冊、查找、管理邏輯從 HeraldDispatcher 中分離出來，
實現更清晰的職責分離和更好的可維護性。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from herald import DispatchContext, HandlerCallable, MiddlewareCallable

from utils.dispatch_types import ComponentHealth


class HandlerEntry:
    """處理器註冊條目的元數據"""
    
    def __init__(
        self,
        handler: "HandlerCallable",
        *,
        name: str,
        audio_type: Optional[str] = None,
        throttle_window: Optional[int] = None,
        throttle_key_factory: Optional[Callable[["DispatchContext"], Optional[str]]] = None,
    ):
        self.handler = handler
        self.name = name
        self.audio_type = audio_type
        self.throttle_window = throttle_window
        self.throttle_key_factory = throttle_key_factory

    def __repr__(self) -> str:
        return f"HandlerEntry(name='{self.name}', audio_type='{self.audio_type}')"


class HandlerRegistry:
    """處理器註冊管理器 - 專責管理 Handler 和 Middleware
    
    職責：
    1. Handler 註冊和查找
    2. Middleware 註冊和管理
    3. 註冊條目的元數據管理
    4. 處理器驗證和健康檢查
    5. 註冊統計和報告
    """

    def __init__(self):
        """初始化處理器註冊管理器"""
        self.event_handlers: Dict[str, HandlerEntry] = {}
        self.middleware_chain: List[Tuple[str, "MiddlewareCallable"]] = []
        self._registration_stats = {
            "handlers_registered": 0,
            "middleware_registered": 0,
            "last_registration": None
        }

    def register_handler(
        self,
        event_type: str,
        handler: "HandlerCallable",
        *,
        name: Optional[str] = None,
        audio_type: Optional[str] = None,
        throttle_window: Optional[int] = None,
        throttle_key_factory: Optional[Callable[["DispatchContext"], Optional[str]]] = None,
    ) -> None:
        """註冊事件處理器
        
        Args:
            event_type: 事件類型
            handler: 處理器函數
            name: 處理器名稱（可選，默認使用函數名）
            audio_type: 音效類型（可選）
            throttle_window: 節流窗口（可選）
            throttle_key_factory: 節流鍵生成器（可選）
            
        Raises:
            ValueError: 如果 event_type 無效
        """
        if not isinstance(event_type, str) or not event_type:
            raise ValueError("event_type must be a non-empty string")
        
        if not callable(handler):
            raise ValueError("handler must be callable")
        
        entry = HandlerEntry(
            handler=handler,
            name=name or getattr(handler, '__name__', 'unknown'),
            audio_type=audio_type,
            throttle_window=throttle_window,
            throttle_key_factory=throttle_key_factory,
        )
        
        # 記錄舊的處理器（如果存在）用於調試
        old_entry = self.event_handlers.get(event_type)
        if old_entry:
            # 可以在這裡添加日誌記錄
            pass
        
        self.event_handlers[event_type] = entry
        self._registration_stats["handlers_registered"] += 1
        self._registration_stats["last_registration"] = event_type

    def register_middleware(
        self, 
        middleware: "MiddlewareCallable", 
        *, 
        name: Optional[str] = None
    ) -> None:
        """註冊中間件
        
        Args:
            middleware: 中間件函數
            name: 中間件名稱（可選，默認使用函數名）
            
        Raises:
            ValueError: 如果 middleware 不可調用
        """
        if not callable(middleware):
            raise ValueError("middleware must be callable")
        
        middleware_name = name or getattr(middleware, '__name__', 'unknown_middleware')
        
        # 檢查是否已存在同名中間件
        existing_names = [mw_name for mw_name, _ in self.middleware_chain]
        if middleware_name in existing_names:
            # 可以選擇拋出異常或者覆蓋，這裡選擇添加序號
            counter = 1
            original_name = middleware_name
            while middleware_name in existing_names:
                middleware_name = f"{original_name}_{counter}"
                counter += 1
        
        self.middleware_chain.append((middleware_name, middleware))
        self._registration_stats["middleware_registered"] += 1

    def get_handler(self, event_type: str) -> Optional[HandlerEntry]:
        """獲取指定事件類型的處理器條目
        
        Args:
            event_type: 事件類型
            
        Returns:
            HandlerEntry 或 None（如果未找到）
        """
        return self.event_handlers.get(event_type)

    def has_handler(self, event_type: str) -> bool:
        """檢查是否存在指定事件類型的處理器
        
        Args:
            event_type: 事件類型
            
        Returns:
            True 如果存在處理器
        """
        return event_type in self.event_handlers

    def get_middleware_chain(self) -> List[Tuple[str, "MiddlewareCallable"]]:
        """獲取中間件鏈
        
        Returns:
            中間件鏈的副本（防止外部修改）
        """
        return self.middleware_chain.copy()

    def get_registered_events(self) -> List[str]:
        """獲取所有已註冊的事件類型
        
        Returns:
            事件類型列表
        """
        return list(self.event_handlers.keys())

    def unregister_handler(self, event_type: str) -> bool:
        """取消註冊處理器
        
        Args:
            event_type: 事件類型
            
        Returns:
            True 如果成功取消註冊，False 如果處理器不存在
        """
        if event_type in self.event_handlers:
            del self.event_handlers[event_type]
            return True
        return False

    def clear_middleware(self) -> int:
        """清除所有中間件
        
        Returns:
            清除的中間件數量
        """
        count = len(self.middleware_chain)
        self.middleware_chain.clear()
        return count

    def get_registration_summary(self) -> Dict[str, Any]:
        """獲取註冊摘要信息
        
        Returns:
            包含註冊統計的字典
        """
        return {
            "total_handlers": len(self.event_handlers),
            "total_middleware": len(self.middleware_chain),
            "registered_events": self.get_registered_events(),
            "middleware_names": [name for name, _ in self.middleware_chain],
            "stats": self._registration_stats.copy()
        }

    def validate_registrations(self) -> List[str]:
        """驗證所有註冊的有效性
        
        Returns:
            問題列表（空列表表示沒有問題）
        """
        issues = []
        
        # 檢查處理器
        for event_type, entry in self.event_handlers.items():
            if not callable(entry.handler):
                issues.append(f"Handler for '{event_type}' is not callable")
            
            if not entry.name:
                issues.append(f"Handler for '{event_type}' has empty name")
            
            if entry.throttle_window is not None and entry.throttle_window < 0:
                issues.append(f"Handler for '{event_type}' has negative throttle_window")
        
        # 檢查中間件
        for name, middleware in self.middleware_chain:
            if not callable(middleware):
                issues.append(f"Middleware '{name}' is not callable")
            
            if not name:
                issues.append("Found middleware with empty name")
        
        return issues

    def get_health_status(self) -> ComponentHealth:
        """獲取 HandlerRegistry 健康狀態
        
        Returns:
            ComponentHealth: 健康狀態報告
        """
        health = ComponentHealth(component_name="HandlerRegistry")
        
        try:
            # 驗證註冊
            issues = self.validate_registrations()
            if issues:
                for issue in issues:
                    health.add_warning(issue)
            
            # 檢查基本狀態
            if not self.event_handlers and not self.middleware_chain:
                health.add_warning("No handlers or middleware registered")
            
            health.last_check = "now"
            
        except Exception as e:
            health.add_error(f"Health check failed: {e}")
        
        return health

    def __len__(self) -> int:
        """返回註冊的處理器總數"""
        return len(self.event_handlers)

    def __contains__(self, event_type: str) -> bool:
        """檢查是否包含指定事件類型的處理器"""
        return event_type in self.event_handlers

    def __repr__(self) -> str:
        return f"HandlerRegistry(handlers={len(self.event_handlers)}, middleware={len(self.middleware_chain)})"