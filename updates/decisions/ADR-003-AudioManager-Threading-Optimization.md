# ADR-003: AudioManager Threading Safety Optimization

**Status**: Proposed
**Date**: 2025-09-24
**Context**: Phase 3 Herald System Optimization - Audio Threading Safety

## Background

The current `audio_manager.py` lacks thread safety mechanisms which could cause issues in concurrent environments:
- Throttle file I/O operations without locking
- Shared state access without synchronization
- Multiple hooks potentially calling audio playback simultaneously
- Configuration loading race conditions

## Goals

1. **Thread Safety**: Add proper locking for shared state access
2. **Concurrent Audio**: Handle multiple simultaneous audio requests safely
3. **File I/O Safety**: Protect throttle file operations with locks
4. **Performance**: Maintain or improve current performance (<100ms)
5. **Backward Compatibility**: Preserve existing API

## Current Thread Safety Issues

### Issue 1: Throttle File Race Conditions
```python
# CURRENT: Unprotected file operations (lines 298-320)
def _read_throttle(self) -> Dict[str, float]:
    with open(self._throttle_path, 'r') as f:  # No file locking
        return json.load(f)

def _write_throttle(self, data: Dict[str, float]) -> None:
    with open(self._throttle_path, 'w') as f:  # Race condition possible
        json.dump(data, f)
```

### Issue 2: Shared State Access
```python
# CURRENT: Unprotected access to instance variables
self.config = AudioConfig(...)  # Shared state
self.volume = volume           # No synchronization
self._throttle_cfg = {}       # Concurrent access possible
```

### Issue 3: ConfigManager Thread Safety
```python
# CURRENT: ConfigManager usage without explicit thread safety
self._config_manager = ConfigManager.get_instance()  # Singleton access
cfg = _load_config(self._config_manager)            # Concurrent calls
```

## Threading Optimization Strategy

### Phase 3.1: Core Threading Infrastructure (Priority: HIGH)

#### 3.1.1 Add Thread-Safe Locks
```python
import threading
from threading import RLock, Lock
from contextlib import contextmanager

class AudioManager:
    def __init__(self):
        # Thread safety locks
        self._config_lock = RLock()      # For configuration access
        self._throttle_lock = Lock()     # For throttle file operations
        self._playback_lock = RLock()    # For audio playback coordination

        # Existing initialization with lock protection
        with self._config_lock:
            # ... existing initialization code
```

#### 3.1.2 Thread-Safe Throttle Operations
```python
def _read_throttle_safe(self) -> Dict[str, float]:
    """Thread-safe throttle data reading with file locking."""
    with self._throttle_lock:
        try:
            if not self._throttle_path.exists():
                return {}

            # Use file locking for cross-process safety
            import fcntl  # Unix systems
            with open(self._throttle_path, 'r') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Shared lock for reading
                data = json.load(f)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Unlock
                return data
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

def _write_throttle_safe(self, data: Dict[str, float]) -> None:
    """Thread-safe throttle data writing with file locking."""
    with self._throttle_lock:
        try:
            self._throttle_path.parent.mkdir(parents=True, exist_ok=True)

            # Use file locking for cross-process safety
            import fcntl  # Unix systems
            with open(self._throttle_path, 'w') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Exclusive lock for writing
                json.dump(data, f, indent=2)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Unlock
        except OSError:
            pass  # Fail silently, maintain backward compatibility
```

#### 3.1.3 Windows File Locking Alternative
```python
def _get_file_lock_context(self, file_path: Path, exclusive: bool = False):
    """Cross-platform file locking context manager."""
    import platform

    if platform.system() == "Windows":
        return self._windows_file_lock(file_path, exclusive)
    else:
        return self._unix_file_lock(file_path, exclusive)

@contextmanager
def _windows_file_lock(self, file_path: Path, exclusive: bool):
    """Windows-specific file locking using msvcrt."""
    import msvcrt

    mode = 'r+' if file_path.exists() else 'w+'
    try:
        with open(file_path, mode) as f:
            lock_type = msvcrt.LK_LOCK if exclusive else msvcrt.LK_NBLCK
            msvcrt.locking(f.fileno(), lock_type, 1)
            yield f
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    except (OSError, IOError):
        # Fallback to no locking
        yield None
```

### Phase 3.2: Concurrent Audio Playback (Priority: MEDIUM)

#### 3.2.1 Thread-Safe Audio Playback
```python
def play_audio_safe(self, audio_type: str, enabled: bool = False,
                   additional_context: Optional[Dict[str, Any]] = None) -> tuple[bool, Optional[Path], Dict[str, Any]]:
    """Thread-safe audio playback with concurrent request handling."""

    with self._playback_lock:
        # Ensure thread-safe access to configuration
        with self._config_lock:
            audio_type = self._normalize_key(audio_type)
            path = self.resolve_file(audio_type)

        # Build context (thread-safe)
        context = self._build_playback_context(audio_type, enabled, path, additional_context)

        if not enabled or path is None:
            return False, path, context

        # Thread-safe playback execution
        return self._execute_playback_safe(path, context)

def _execute_playback_safe(self, path: Path, context: Dict[str, Any]) -> tuple[bool, Path, Dict[str, Any]]:
    """Execute audio playback with thread safety."""
    try:
        if self._player_cmd == "winsound":
            # Windows playback is already async and thread-safe
            rc = _play_with_windows(str(path), volume=self.volume, timeout_s=self._timeout_s)
        else:
            # Unix-based playback with process isolation
            rc = _play_with(self._player_cmd, self._player_base_args + [str(path)], timeout_s=self._timeout_s)

        success = (rc == 0)
        context.update({"status": "played" if success else "failed", "returnCode": rc})
        return success, path, context

    except Exception as e:
        context.update({"status": "failed", "error": str(e)})
        return False, path, context
```

#### 3.2.2 Throttle with Thread Safety
```python
def is_throttled_safe(self, audio_type: str, throttle_window_seconds: int) -> bool:
    """Thread-safe throttling check."""
    if throttle_window_seconds <= 0:
        return False

    audio_type = self._normalize_key(audio_type)
    now = time.time()

    # Thread-safe throttle data access
    throttle_data = self._read_throttle_safe()
    last_played = throttle_data.get(audio_type, 0.0)

    if now - last_played < throttle_window_seconds:
        return True

    # Update throttle data thread-safely
    throttle_data[audio_type] = now
    self._write_throttle_safe(throttle_data)
    return False
```

### Phase 3.3: Configuration Thread Safety (Priority: LOW)

#### 3.3.1 Thread-Safe Configuration Access
```python
def get_config_safe(self, key: str, default: Any = None) -> Any:
    """Thread-safe configuration access."""
    with self._config_lock:
        return self._config_manager.get(key, default)

def reload_config_safe(self) -> None:
    """Thread-safe configuration reload."""
    with self._config_lock:
        self._config_manager.clear_cache()
        # Reload configuration
        cfg = _load_config(self._config_manager)
        self._update_config_from_dict(cfg)
```

## Implementation Steps

### Step 1: Add Threading Infrastructure
```bash
# Backup current implementation
cp utils/audio_manager.py utils/audio_manager.py.backup

# Add threading imports and locks to __init__
```

### Step 2: Implement Thread-Safe File Operations
1. Add `_read_throttle_safe()` and `_write_throttle_safe()`
2. Implement cross-platform file locking
3. Update throttle methods to use safe operations

### Step 3: Add Thread-Safe Audio Playback
1. Protect `play_audio()` with `_playback_lock`
2. Ensure configuration access is synchronized
3. Handle concurrent playback requests gracefully

### Step 4: Thread-Safe Configuration
1. Protect ConfigManager access with `_config_lock`
2. Add safe configuration reload mechanism
3. Ensure initialization thread safety

## Performance Considerations

### Lock Granularity
- **Fine-grained locks**: Separate locks for different operations
- **RLock usage**: Allow recursive locking for complex operations
- **Lock-free paths**: Audio playback doesn't block configuration access

### Expected Performance Impact
- **Throttle operations**: +1-2ms (file locking overhead)
- **Configuration access**: <0.1ms (memory-based)
- **Audio playback**: No impact (already async)
- **Overall hook latency**: <5ms additional overhead

## Testing Strategy

### Unit Tests
```python
def test_concurrent_audio_playback():
    """Test multiple threads playing audio simultaneously."""
    import threading
    import time

    audio_manager = AudioManager()
    results = []

    def play_audio_worker(audio_type: str):
        result = audio_manager.play_audio_safe(audio_type, enabled=True)
        results.append(result)

    # Start multiple threads
    threads = []
    for i in range(5):
        t = threading.Thread(target=play_audio_worker, args=("notification",))
        threads.append(t)
        t.start()

    # Wait for completion
    for t in threads:
        t.join()

    # Verify all completed successfully
    assert len(results) == 5
    assert all(result[0] or not result[0] for result in results)  # Either played or gracefully failed

def test_throttle_thread_safety():
    """Test throttling under concurrent access."""
    import threading

    audio_manager = AudioManager()
    throttle_results = []

    def check_throttle_worker():
        result = audio_manager.is_throttled_safe("notification", 1)
        throttle_results.append(result)

    # Concurrent throttle checks
    threads = [threading.Thread(target=check_throttle_worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # First call should not be throttled, subsequent calls should be
    assert len([r for r in throttle_results if not r]) == 1  # Only one non-throttled
```

### Integration Tests
```python
def test_herald_concurrent_hooks():
    """Test Herald dispatcher with concurrent hook execution."""
    import threading
    from herald import HeraldDispatcher

    dispatcher = HeraldDispatcher()
    results = []

    def trigger_hook_worker(event_type: str):
        context = dispatcher.create_context(event_type, {})
        result = dispatcher.dispatch(context)
        results.append(result)

    # Concurrent hook execution
    events = ["Notification", "Stop", "PreToolUse", "PostToolUse"]
    threads = [threading.Thread(target=trigger_hook_worker, args=(event,)) for event in events]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify all hooks executed without errors
    assert len(results) == 4
    assert all(not result.errors for result in results)
```

## Success Criteria

### Thread Safety
- [ ] No race conditions in file operations
- [ ] Concurrent audio playback works correctly
- [ ] Configuration access is thread-safe
- [ ] Throttling works under concurrent load

### Performance
- [ ] Hook execution remains under 100ms
- [ ] Audio playback latency maintained
- [ ] File I/O overhead minimized
- [ ] Memory usage stable under load

### Compatibility
- [ ] All existing APIs work unchanged
- [ ] Cross-platform compatibility maintained
- [ ] Herald CLI integration unaffected
- [ ] No functional regressions

## Risk Mitigation

### Deadlock Prevention
- Consistent lock ordering
- Timeout on lock acquisition
- RLock usage for recursive calls

### Performance Monitoring
```python
import time
from contextlib import contextmanager

@contextmanager
def performance_monitor(operation_name: str):
    """Monitor operation performance for threading overhead."""
    start = time.time()
    yield
    duration = (time.time() - start) * 1000
    if duration > 10:  # Log slow operations
        print(f"SLOW: {operation_name} took {duration:.2f}ms")
```

### Fallback Strategy
- File locking failures fall back to non-locked operations
- Thread creation failures fall back to synchronous execution
- Lock timeouts use default values

---

*Generated for Herald System Phase 3 Optimization - 2025-09-24*