#!/usr/bin/env python3
"""測試 MiddlewareRunner 的綜合測試套件"""
import unittest
import sys
from unittest.mock import Mock
from pathlib import Path

# 添加專案根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from herald import DispatchContext
from utils.middleware_runner import MiddlewareRunner, MiddlewareExecutionResult


class TestMiddlewareExecutionResult(unittest.TestCase):
    """測試 MiddlewareExecutionResult 類別"""
    
    def test_initial_state(self):
        """測試初始狀態"""
        context = DispatchContext("test", {})
        result = MiddlewareExecutionResult(context)
        
        assert result.context == context
        assert result.executed_count == 0
        assert result.errors == []
        assert result.stopped_early is False
        assert result.middleware_notes == []
    
    def test_add_successful_execution(self):
        """測試成功執行記錄"""
        context = DispatchContext("test", {})
        result = MiddlewareExecutionResult(context)
        
        result.add_execution("test_middleware", success=True)
        
        assert result.executed_count == 1
        assert result.errors == []
        assert "Executed middleware: test_middleware" in result.middleware_notes
    
    def test_add_failed_execution(self):
        """測試失敗執行記錄"""
        context = DispatchContext("test", {})
        result = MiddlewareExecutionResult(context)
        
        result.add_execution("test_middleware", success=False, error="test error")
        
        assert result.executed_count == 1
        assert "middleware:test_middleware - test error" in result.errors
        assert len(result.middleware_notes) == 0
    
    def test_should_stop_when_stop_dispatch(self):
        """測試當 context.stop_dispatch 為 True 時停止"""
        context = DispatchContext("test", {})
        context.stop_dispatch = True
        result = MiddlewareExecutionResult(context)
        
        assert result.should_stop() is True
    
    def test_should_stop_when_stopped_early(self):
        """測試當 stopped_early 為 True 時停止"""
        context = DispatchContext("test", {})
        result = MiddlewareExecutionResult(context)
        result.stopped_early = True
        
        assert result.should_stop() is True


class TestMiddlewareRunner(unittest.TestCase):
    """測試 MiddlewareRunner 類別"""
    
    def setUp(self):
        """每個測試方法前的設置"""
        self.runner = MiddlewareRunner()
        self.context = DispatchContext("test", {})
    
    def test_initial_stats(self):
        """測試初始統計狀態"""
        stats = self.runner.get_execution_summary()
        
        assert stats["total_executions"] == 0
        assert stats["successful_executions"] == 0
        assert stats["failed_executions"] == 0
        assert stats["success_rate"] == 0
        assert stats["last_execution"] is None
    
    def test_empty_middleware_list(self):
        """測試空中間件列表"""
        result = self.runner.run_middleware([], self.context)
        
        assert result == self.context
        stats = self.runner.get_execution_summary()
        assert stats["total_executions"] == 0
    
    def test_single_successful_middleware(self):
        """測試單個成功中間件"""
        def test_middleware(ctx):
            ctx.notes.append("test note")
            return ctx
        
        middleware_list = [("test_mw", test_middleware)]
        result = self.runner.run_middleware(middleware_list, self.context)
        
        assert "test note" in result.notes
        assert "Executed middleware: test_mw" in result.notes
        
        stats = self.runner.get_execution_summary()
        assert stats["total_executions"] == 1
        assert stats["successful_executions"] == 1
        assert stats["success_rate"] == 100
    
    def test_middleware_returns_new_context(self):
        """測試中間件返回新上下文"""
        def context_changing_middleware(ctx):
            new_context = DispatchContext("new_event", {"new": "data"})
            new_context.notes = ctx.notes.copy()
            new_context.errors = ctx.errors.copy()
            return new_context
        
        middleware_list = [("context_changer", context_changing_middleware)]
        result = self.runner.run_middleware(middleware_list, self.context)
        
        assert result.event_type == "new_event"
        assert result.payload == {"new": "data"}
    
    def test_middleware_with_exception(self):
        """測試中間件異常處理"""
        def failing_middleware(ctx):
            raise ValueError("test error")
        
        def working_middleware(ctx):
            ctx.notes.append("after failure")
            return ctx
        
        middleware_list = [
            ("failing_mw", failing_middleware),
            ("working_mw", working_middleware)
        ]
        
        result = self.runner.run_middleware(middleware_list, self.context)
        
        # 檢查錯誤處理
        assert any("middleware:failing_mw - test error" in error for error in result.errors)
        
        # 檢查後續中間件繼續執行
        assert "after failure" in result.notes
        assert "Executed middleware: working_mw" in result.notes
        
        # 檢查統計
        stats = self.runner.get_execution_summary()
        assert stats["total_executions"] == 1
        assert stats["failed_executions"] == 1
    
    def test_middleware_early_stop(self):
        """測試中間件提前停止"""
        def stopping_middleware(ctx):
            ctx.stop_dispatch = True
            return ctx
        
        def unreachable_middleware(ctx):
            ctx.notes.append("should not reach")
            return ctx
        
        middleware_list = [
            ("stopper", stopping_middleware),
            ("unreachable", unreachable_middleware)
        ]
        
        result = self.runner.run_middleware(middleware_list, self.context)
        
        assert result.stop_dispatch is True
        assert "should not reach" not in result.notes
        assert "Executed middleware: stopper" in result.notes
    
    def test_middleware_returns_none(self):
        """測試中間件返回 None"""
        def none_returning_middleware(ctx):
            ctx.notes.append("processed but returns none")
            return None
        
        middleware_list = [("none_mw", none_returning_middleware)]
        result = self.runner.run_middleware(middleware_list, self.context)
        
        assert "processed but returns none" in result.notes
        assert "Executed middleware: none_mw" in result.notes
    
    def test_middleware_returns_unexpected_type(self):
        """測試中間件返回意外類型"""
        def weird_middleware(ctx):
            return "unexpected string"
        
        middleware_list = [("weird_mw", weird_middleware)]
        result = self.runner.run_middleware(middleware_list, self.context)
        
        warning_found = any("returned unexpected type" in note for note in result.notes)
        assert warning_found
    
    def test_non_callable_middleware(self):
        """測試不可調用的中間件"""
        middleware_list = [("not_callable", "this is not callable")]
        result = self.runner.run_middleware(middleware_list, self.context)
        
        assert any("not callable" in error for error in result.errors)
        
        stats = self.runner.get_execution_summary()
        assert stats["failed_executions"] == 1


class TestMiddlewareValidation(unittest.TestCase):
    """測試中間件驗證功能"""
    
    def setUp(self):
        self.runner = MiddlewareRunner()
    
    def test_validate_empty_list(self):
        """測試驗證空列表"""
        issues = self.runner.validate_middleware_chain([])
        assert issues == []
    
    def test_validate_valid_middleware(self):
        """測試驗證有效中間件"""
        def valid_mw(ctx):
            return ctx
        
        middleware_list = [("valid", valid_mw)]
        issues = self.runner.validate_middleware_chain(middleware_list)
        assert issues == []
    
    def test_validate_empty_name(self):
        """測試空名稱驗證"""
        def valid_mw(ctx):
            return ctx
        
        middleware_list = [("", valid_mw)]
        issues = self.runner.validate_middleware_chain(middleware_list)
        assert "empty name" in issues[0]
    
    def test_validate_duplicate_names(self):
        """測試重複名稱驗證"""
        def mw1(ctx):
            return ctx
        def mw2(ctx):
            return ctx
        
        middleware_list = [("duplicate", mw1), ("duplicate", mw2)]
        issues = self.runner.validate_middleware_chain(middleware_list)
        assert "Duplicate middleware name" in issues[0]
    
    def test_validate_non_callable(self):
        """測試不可調用驗證"""
        middleware_list = [("bad", "not callable")]
        issues = self.runner.validate_middleware_chain(middleware_list)
        assert "not callable" in issues[0]


class TestMiddlewareStats(unittest.TestCase):
    """測試中間件統計功能"""
    
    def setUp(self):
        self.runner = MiddlewareRunner()
        self.context = DispatchContext("test", {})
    
    def test_stats_after_successful_run(self):
        """測試成功運行後的統計"""
        def success_mw(ctx):
            return ctx
        
        middleware_list = [("success", success_mw)]
        self.runner.run_middleware(middleware_list, self.context)
        
        stats = self.runner.get_execution_summary()
        assert stats["total_executions"] == 1
        assert stats["successful_executions"] == 1
        assert stats["success_rate"] == 100
        assert stats["last_execution"]["middleware_count"] == 1
        assert stats["last_execution"]["errors"] == 0
    
    def test_stats_after_failed_run(self):
        """測試失敗運行後的統計"""
        def failing_mw(ctx):
            raise Exception("test failure")
        
        middleware_list = [("failing", failing_mw)]
        self.runner.run_middleware(middleware_list, self.context)
        
        stats = self.runner.get_execution_summary()
        assert stats["total_executions"] == 1
        assert stats["successful_executions"] == 0
        assert stats["failed_executions"] == 1
        assert stats["success_rate"] == 0
    
    def test_stats_reset(self):
        """測試統計重置"""
        def test_mw(ctx):
            return ctx
        
        # 執行一些中間件
        middleware_list = [("test", test_mw)]
        self.runner.run_middleware(middleware_list, self.context)
        
        # 重置統計
        self.runner.reset_stats()
        
        stats = self.runner.get_execution_summary()
        assert stats["total_executions"] == 0
        assert stats["successful_executions"] == 0
        assert stats["failed_executions"] == 0


class TestMiddlewareHealth(unittest.TestCase):
    """測試中間件健康檢查"""
    
    def setUp(self):
        self.runner = MiddlewareRunner()
    
    def test_initial_health(self):
        """測試初始健康狀態"""
        health = self.runner.get_health_status()
        assert health.component_name == "MiddlewareRunner"
        assert health.is_healthy
    
    def test_health_with_low_success_rate(self):
        """測試低成功率的健康狀態"""
        # 模擬低成功率統計
        self.runner.execution_stats = {
            "total_executions": 10,
            "successful_executions": 5,
            "failed_executions": 5,
            "last_execution": None
        }
        
        health = self.runner.get_health_status()
        assert len(health.warnings) > 0
        assert any("Low success rate" in warning for warning in health.warnings)
    
    def test_health_with_high_failure_count(self):
        """測試高失敗次數的健康狀態"""
        # 模擬高失敗次數統計
        self.runner.execution_stats = {
            "total_executions": 20,
            "successful_executions": 20,
            "failed_executions": 15,  # 超過閾值
            "last_execution": None
        }
        
        health = self.runner.get_health_status()
        assert len(health.warnings) > 0
        assert any("High failure count" in warning for warning in health.warnings)


class TestMiddlewareRunnerIntegration(unittest.TestCase):
    """測試 MiddlewareRunner 整合功能"""
    
    def test_repr(self):
        """測試字符串表示"""
        runner = MiddlewareRunner()
        repr_str = repr(runner)
        
        assert "MiddlewareRunner" in repr_str
        assert "executions=0" in repr_str
        assert "success_rate=0.0%" in repr_str


if __name__ == "__main__":
    unittest.main(verbosity=2)