"""中間件執行引擎 - 專責執行中間件鏈

這個模組將中間件執行邏輯從 HeraldDispatcher 中分離出來，
提供統一、可靠的中間件執行機制。
"""
from __future__ import annotations

from typing import List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from herald import DispatchContext, MiddlewareCallable

from utils.dispatch_types import ComponentHealth


class MiddlewareExecutionResult:
    """中間件執行結果"""
    
    def __init__(self, context: "DispatchContext"):
        self.context = context
        self.executed_count = 0
        self.errors: List[str] = []
        self.stopped_early = False
        self.middleware_notes: List[str] = []

    def add_execution(self, middleware_name: str, success: bool = True, error: str = None):
        """記錄中間件執行"""
        self.executed_count += 1
        if not success and error:
            self.errors.append(f"middleware:{middleware_name} - {error}")
        if success:
            self.middleware_notes.append(f"Executed middleware: {middleware_name}")

    def should_stop(self) -> bool:
        """檢查是否應該停止執行"""
        return self.context.stop_dispatch or self.stopped_early


class MiddlewareRunner:
    """中間件執行引擎 - 專責執行中間件鏈
    
    職責：
    1. 按順序執行中間件鏈
    2. 處理中間件錯誤和異常
    3. 管理執行流程控制
    4. 提供執行狀態報告
    5. 支援中間件鏈驗證
    """

    def __init__(self):
        """初始化中間件執行引擎"""
        self.execution_stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "last_execution": None
        }

    def run_middleware(
        self,
        middleware_list: List[Tuple[str, "MiddlewareCallable"]],
        context: "DispatchContext"
    ) -> "DispatchContext":
        """執行中間件鏈
        
        Args:
            middleware_list: 中間件列表 [(name, middleware), ...]
            context: 分派上下文
            
        Returns:
            DispatchContext: 處理後的上下文（可能是修改後的新上下文）
        """
        if not middleware_list:
            return context
        
        execution_result = MiddlewareExecutionResult(context)
        current_context = context
        
        try:
            for mw_name, middleware in middleware_list:
                # 檢查是否應該停止執行
                if execution_result.should_stop():
                    execution_result.stopped_early = True
                    break
                
                try:
                    # 執行中間件
                    result = self._execute_single_middleware(middleware, current_context, mw_name)
                    
                    # 處理中間件返回結果
                    if isinstance(result, type(current_context)):
                        # 如果中間件返回新的上下文，使用它
                        current_context = result
                        execution_result.context = current_context
                    
                    execution_result.add_execution(mw_name, success=True)
                    
                except Exception as exc:
                    # 中間件異常處理 - 不中斷整個鏈
                    error_msg = str(exc)
                    execution_result.add_execution(mw_name, success=False, error=error_msg)
                    current_context.errors.append(f"middleware:{mw_name} - {exc}")
                    
                    # 更新統計
                    self.execution_stats["failed_executions"] += 1
                    
                    # 繼續執行下一個中間件（容錯機制）
                    continue
            
            # 更新執行統計
            self._update_execution_stats(execution_result)
            
            # 將中間件註記添加到上下文
            if execution_result.middleware_notes:
                current_context.notes.extend(execution_result.middleware_notes)
            
        except Exception as exc:
            # 執行引擎本身的異常處理
            current_context.errors.append(f"middleware_runner - {exc}")
            self.execution_stats["failed_executions"] += 1
        
        return current_context

    def _execute_single_middleware(
        self,
        middleware: "MiddlewareCallable",
        context: "DispatchContext",
        name: str
    ) -> "DispatchContext":
        """執行單個中間件
        
        Args:
            middleware: 中間件函數
            context: 當前上下文
            name: 中間件名稱
            
        Returns:
            DispatchContext: 處理後的上下文
        """
        if not callable(middleware):
            raise ValueError(f"Middleware '{name}' is not callable")
        
        # 執行中間件
        result = middleware(context)
        
        # 驗證返回結果
        if result is None:
            # 如果中間件沒有返回值，使用原上下文
            return context
        elif hasattr(result, 'event_type'):
            # 如果返回的是 DispatchContext 類型的對象
            return result
        else:
            # 其他類型的返回值，記錄警告但不中斷執行
            context.notes.append(f"Middleware '{name}' returned unexpected type: {type(result)}")
            return context

    def _update_execution_stats(self, execution_result: MiddlewareExecutionResult) -> None:
        """更新執行統計信息"""
        self.execution_stats["total_executions"] += 1
        if not execution_result.errors:
            self.execution_stats["successful_executions"] += 1
        self.execution_stats["last_execution"] = {
            "middleware_count": execution_result.executed_count,
            "errors": len(execution_result.errors),
            "stopped_early": execution_result.stopped_early
        }

    def validate_middleware_chain(
        self,
        middleware_list: List[Tuple[str, "MiddlewareCallable"]]
    ) -> List[str]:
        """驗證中間件鏈的有效性
        
        Args:
            middleware_list: 中間件列表
            
        Returns:
            問題列表（空列表表示沒有問題）
        """
        issues = []
        
        if not middleware_list:
            return issues
        
        seen_names = set()
        for i, (name, middleware) in enumerate(middleware_list):
            # 檢查中間件名稱
            if not name:
                issues.append(f"Middleware at index {i} has empty name")
            elif name in seen_names:
                issues.append(f"Duplicate middleware name: '{name}'")
            else:
                seen_names.add(name)
            
            # 檢查中間件可調用性
            if not callable(middleware):
                issues.append(f"Middleware '{name}' at index {i} is not callable")
        
        return issues

    def get_execution_summary(self) -> dict:
        """獲取執行摘要統計
        
        Returns:
            包含執行統計的字典
        """
        total = self.execution_stats["total_executions"]
        successful = self.execution_stats["successful_executions"]
        failed = self.execution_stats["failed_executions"]
        
        return {
            "total_executions": total,
            "successful_executions": successful,
            "failed_executions": failed,
            "success_rate": (successful / total * 100) if total > 0 else 0,
            "last_execution": self.execution_stats["last_execution"]
        }

    def reset_stats(self) -> None:
        """重置執行統計"""
        self.execution_stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "last_execution": None
        }

    def get_health_status(self) -> ComponentHealth:
        """獲取 MiddlewareRunner 健康狀態
        
        Returns:
            ComponentHealth: 健康狀態報告
        """
        health = ComponentHealth(component_name="MiddlewareRunner")
        
        try:
            # 檢查執行統計
            stats = self.get_execution_summary()
            
            if stats["total_executions"] > 0:
                if stats["success_rate"] < 80:
                    health.add_warning(f"Low success rate: {stats['success_rate']:.1f}%")
                
                if stats["failed_executions"] > 10:
                    health.add_warning(f"High failure count: {stats['failed_executions']}")
            
            # 檢查最近執行狀態
            last_execution = stats.get("last_execution")
            if last_execution and last_execution.get("errors", 0) > 0:
                health.add_warning(f"Last execution had {last_execution['errors']} errors")
            
            health.last_check = "now"
            
        except Exception as e:
            health.add_error(f"Health check failed: {e}")
        
        return health

    def __repr__(self) -> str:
        stats = self.get_execution_summary()
        return f"MiddlewareRunner(executions={stats['total_executions']}, success_rate={stats['success_rate']:.1f}%)"