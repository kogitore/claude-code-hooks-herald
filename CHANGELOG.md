# Changelog

All notable changes to this project will be documented in this file. The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and adheres to [Semantic Versioning](https://semver.org/).

Commit messages are recommended to follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

## [Unreleased]

## [0.5.0-dev] - 2025-12-01
### 🚀 Architecture Modernization & Notion Integration

Major release featuring Herald toolkit consolidation, Notion project/task management, and Skill Auto-Activation system. Based on [Anthropic Engineering Blog](https://www.anthropic.com/engineering/claude-code-best-practices) and patterns from [claude-code-infrastructure-showcase](https://github.com/diet103/claude-code-infrastructure-showcase).

#### Added

##### **Herald Toolkit** (`.claude/herald/`)
New unified toolkit package for Claude Code enhancements:
- **`herald/__init__.py`** - Core package with version management
- **`herald/notion/`** - Notion API integration module
- **`herald/dev-tools/`** - Development utilities (health check, integration tests)

##### **Notion Integration** (`.claude/herald/notion/`)
Complete project and task management system:
- **`client.py`** - `NotionClient` API wrapper with context manager support
- **`project.py`** - `ProjectManager` with auto-detection using folder name
- **`tasks.py`** - `TaskManager` with `TaskDefinition`, `TaskPriority`, `TaskType` enums
- **`cli.py`** - CLI interface for project/task operations

Usage:
```bash
uv run python .claude/herald/notion/cli.py project info
uv run python .claude/herald/notion/cli.py tasks create
```

##### **Skills System** (`.claude/skills/`)
Extensible skill auto-activation framework:
- **`skill-rules.json`** - JSON configuration for 8 skills with triggers
  - `test`, `refactor`, `debug`, `review`, `docs`, `hooks`, `notion-integration`, `security`
  - Supports keyword matching and regex intent patterns
  - Traditional Chinese keywords support (測試, 重構, 錯誤, etc.)
- **`skill_rules.py`** - Skill rules loader with caching and fallback
- **`notion-integration/SKILL.md`** - Notion skill documentation

##### **Slash Commands** (`.claude/commands/`)
- **`/notion-sync`** - Sync current project to Notion
- **`/notion-task`** - Quick task creation with type inference

##### **Block-at-Commit Strategy** (`pre_tool_use.py`)
- Only blocks at `git commit` time, not during Edit/Write operations
- Gate file mechanism: `/tmp/hooks-herald-tests-pass`
- Bypass with `HOOKS_SKIP_COMMIT_GATE=1`

##### **Test Coverage**
- `test_skill_suggestions.py`: 12 tests for skill detection
- `test_commit_gate.py`: 9 tests for commit gate behavior
- Enhanced `conftest.py` with `build_default_dispatcher()`

#### Changed

##### **Directory Restructure**
- Moved `scripts/notion/` → `.claude/herald/notion/`
- Moved `scripts/*.sh` → `.claude/herald/dev-tools/`
- Deleted root `scripts/` directory (keeps project root clean)

##### **Hook System Modernization**
All hooks simplified with function-based handlers:
- **`herald.py`** - Direct handler dispatch (no middleware layers)
- **`session_start.py`** / **`session_end.py`** - Minimal session tracking
- **`user_prompt_submit.py`** - Now uses `skill_rules.py` for dynamic skill suggestions
- **`pre_tool_use.py`** / **`post_tool_use.py`** - Audio-only paths, simplified security

##### **Type Safety** (Python 3.10+)
- `dict[str, object]` instead of `Dict[str, Any]`
- `str | None` union syntax (PEP 604)
- `from __future__ import annotations` throughout
- `Callable` from `collections.abc`

##### **Pyproject Configuration**
```toml
[project.scripts]
herald-notion = "herald.notion.cli:main"

[tool.hatch.build.targets.wheel]
packages = [".claude/herald"]
```

#### Fixed
- `test_audio_played_and_timeout.py`: Duplicate shebang/imports causing SyntaxError
- Import path issues after directory restructure
- Module resolution for herald package

#### Documentation
- Added `docs/OPTIMIZATION_ROADMAP.md`: Community best practices roadmap
- Added `docs/dev/` pattern for development context preservation

---

## [0.4.0-dev] - 2025-09-24
### 🔥 Major System Simplification - Linus-Style Architecture Cleanup

**"What the f*ck was wrong with us? We had 20+ files to play a sound when something happens. This has been fixed."** - *Linus Review*

#### **The Problem**: Enterprise Java Hell
- **40+ Python files** doing what should be simple audio notification
- **Complex abstraction layers**: MiddlewareRunner, HandlerRegistry, AudioDispatcher
- **Over-engineering**: Multiple classes, registries, and middleware for basic functionality
- **Technical debt**: Duplicate code, unused abstractions, theoretical edge cases

#### **The Solution**: Brutal Simplification

##### **Phase 1: Remove Abstraction Hell**
###### Deleted
- ❌ **`middleware_runner.py`** - Unnecessary middleware execution engine
- ❌ **`handler_registry.py`** - Registry pattern bullshit for 8 event types
- ❌ **`audio_dispatcher.py`** - Another layer of abstraction over AudioManager
- ❌ **`base_hook.py`** - Useless abstraction returning empty dicts
- ❌ **`dispatch_types.py`** - Type theater for simple operations
- ❌ **`session_storage.py`** (then recreated when needed) - Simplified session management
- ❌ **`subagent_stop.py`** - Identical duplicate of stop.py

###### Changed
- **Herald Dispatcher**: From 500+ lines of enterprise complexity to **direct dictionary lookup**
- **Event Handling**: From middleware→registry→handler chain to **simple function calls**
- **Audio Logic**: From multi-layer dispatch to **direct AudioManager integration**
- **Stop Events**: Merged duplicate logic into single implementation with shared handler

##### **Phase 2: Test Suite Cleanup**
###### Removed (9 files eliminated)
- ❌ **`test_middleware_runner.py`** - Testing deleted functionality
- ❌ **`test_handler_registry.py`** - Testing deleted abstraction
- ❌ **`test_audio_dispatcher.py`** - Testing removed layer
- ❌ **`test_decision_api_refactor.py`** - Duplicate test logic
- ❌ **`test_constants.py`** - Testing constant definitions (pointless)
- ❌ **`test_json_only.py`** - Simple compatibility test
- ❌ **`test_throttle.py`** - Logic integrated into main tests
- ❌ **`test_subagent_stop.py`** - Duplicate of stop test
- ❌ **`run_tests.py`** - Unnecessary test runner (use pytest directly)

###### Results
- **Test Files**: 19 → 8 files (-58% reduction)
- **Test Code**: 1,772 → 674 lines (-62% reduction)
- **Test Focus**: Removed edge case testing, kept core functionality validation

##### **Phase 3: File System Cleanup**
###### Removed Temporary/Development Files
- ❌ **`temp_test_config_dir/`** - Temporary test configuration directory
- ❌ **`test_audio_basic.py`** - Development audio testing script
- ❌ **`test_audio_threading.py`** - Development threading tests
- ❌ **`*.backup`** files - Development backup files
- ❌ **`*.example`** files - Unnecessary example configurations

### **Results: From Enterprise Hell to Working Code**

#### **File Count Reduction**
- **Main Files**: 20+ → 14 files (-30%)
- **Test Files**: 19 → 8 files (-58%)
- **Utils Files**: 10+ → 6 files (-40%)
- **Total Project**: 40+ → 22 files (-45%)

#### **Code Simplification**
- **Herald Dispatcher**: Direct dictionary lookup, no middleware bullshit
- **Event Processing**: Function calls instead of class hierarchies
- **Audio System**: Direct AudioManager usage, no extra layers
- **Stop Logic**: Single implementation handles both Stop and SubagentStop

#### **Maintainability Gains**
- **Readable Code**: Junior developers can understand the flow
- **Simple Debugging**: No complex middleware chains to trace
- **Fast Changes**: Modifications take minutes, not hours
- **Clear Architecture**: 8 hooks + 6 utils + 8 tests = done

#### **Performance Impact**
- **Startup Time**: Faster initialization (fewer imports, less object creation)
- **Execution Path**: Direct function calls vs. multi-layer delegation
- **Memory Usage**: Eliminated unnecessary object hierarchies
- **Audio Playback**: Fixed throttle configuration conflicts

### **What Survived the Purge**
#### **Essential Main Files** (8)
- ✅ `herald.py` - Core dispatcher (massively simplified)
- ✅ `notification.py`, `stop.py`, `pre_tool_use.py`, `post_tool_use.py`
- ✅ `user_prompt_submit.py`, `session_start.py`, `session_end.py`

#### **Essential Utils** (6)
- ✅ `audio_manager.py` - Does actual work (playing sounds)
- ✅ `decision_api.py` - Security decisions (actually needed)
- ✅ `config_manager.py` - Configuration (used by other utils)
- ✅ `common_io.py`, `constants.py`, `session_storage.py`

#### **Essential Tests** (8)
- ✅ Core functionality tests for each hook
- ✅ Integration testing for Herald dispatcher
- ✅ Audio system validation

### **Linus Verdict**
**Before**: "*This codebase is a total and utter disaster in every single respect*"
**After**: "*This can work. 22 files, clear responsibilities, no bullshit, focused tests. The code is no longer shit - it's been fixed.*"

### **Breaking Changes**
- None. **100% backward compatibility** maintained
- All existing `--hook` commands work identically
- Configuration files unchanged
- Audio functionality fully preserved

### **Files Removed**
- **9 abstraction layer files** - middleware_runner.py, handler_registry.py, audio_dispatcher.py, etc.
- **9 test files** - removed redundant and over-engineered tests
- **5+ temporary files** - cleanup of development artifacts
- **Multiple backup files** - removed .backup and .example files

## [0.3.0-dev] - 2025-09-24
### 🔧 Initial Architecture Assessment and Preparation

#### **Discovery Phase**
##### **Codebase Analysis**
- **Identified Over-Engineering**: Found 20+ files implementing basic audio notification system
- **Architecture Problems**: Multiple unnecessary abstraction layers discovered
- **Code Duplication**: stop.py and subagent_stop.py found to be identical
- **Test Bloat**: 19 test files with significant redundancy identified

##### **Performance Baseline**
- **Execution Path Analysis**: Traced complex middleware→registry→handler chains
- **Audio System Review**: Found working AudioManager buried under abstraction layers
- **Configuration Issues**: Discovered throttle setting conflicts between herald.py and audio_config.json

#### **Planning and Preparation**
##### **Added (Development Tools)**
- **Architecture Analysis Files**: HOOKS_ARCHITECTURE.md, HOOKS_ARCHITECTURE_Linus_fix.md
- **Cleanup Guidelines**: Detailed step-by-step simplification plan
- **Linus Review Mode**: Brutal honesty assessment methodology

##### **Fixed (Critical Issues)**
- **Audio Throttle Conflict**: Corrected DEFAULT_THROTTLE_WINDOWS in herald.py to match audio_config.json (600s → 120s)
- **Missing Task Completion Audio**: Resolved throttling preventing completion sound playback
- **Import Dependencies**: Fixed session_storage import issues after cleanup

#### **Assessment Results**
##### **Identified for Removal**
- **Abstraction Layers**: 7+ unnecessary utility files
- **Duplicate Logic**: Multiple identical implementations
- **Over-Testing**: 50%+ of tests covering theoretical edge cases
- **Temporary Files**: Development artifacts and backup files

##### **Marked for Preservation**
- **Core Functionality**: 8 essential hook handlers
- **Working Systems**: AudioManager, DecisionAPI, ConfigManager
- **Essential Tests**: Core functionality and integration tests

### **Preparation Complete**
- **Backup Created**: Full system backup before major refactoring
- **Plan Documented**: Comprehensive cleanup strategy established
- **Tools Ready**: Analysis and guidance documentation prepared
- **Assessment Done**: Clear understanding of what works vs. what's bloat

This version represents the *planning and assessment phase* before the major v0.4.0 simplification effort.

## [0.2.0] - 2025-09-22
### Added
- **Complete Claude Code Events Support**: 8/9 official events implemented (UserPromptSubmit, PreToolUse, PostToolUse, SessionStart, SessionEnd)
- **Claude Code Field Compatibility**: Full support for both legacy (`tool`/`toolInput`) and standard (`tool_name`/`tool_input`) field formats
- **Comprehensive Test Suite**: Enhanced test coverage with 9 passing tests including field precedence and error handling scenarios
- **Decision API Security**: Advanced security policies with command pattern matching, file protection, and package installation validation
- Herald dispatcher (`.claude/hooks/herald.py`) with Decision API integration for Pre/PostToolUse and Stop events.
- BaseHook framework plus Notification/Stop/SubagentStop implementations that reuse shared audio handling.
- Configurable `decision_policy.json` (with `decision_policy.example.json` template + ADR 0003) to extend allow/deny/ask/block rules without losing built-in safeguards.
- TagMatcher library (`system:dangerous`, `package:install`, `git:destructive`, etc.) with severity ranking for policy responses; ADR 0004 documents the design.

### Changed
- **Field Extraction Logic**: Enhanced `_extract_tool()` and `_extract_tool_input()` methods to support Claude Code standard field names
- **Test Infrastructure**: Added direct hook testing utilities (`_invoke_pre_tool_use_direct`) and decision parsing helpers
- **Roadmap Corrections**: Updated roadmap v1.6 to reflect actual 8/9 event completion status and removed non-official Error event
- `.claude/settings.json` now routes all official events through the Herald dispatcher.
- README (EN/繁中) updated to describe dispatcher architecture, Decision API, and CLI usage.

### Fixed
- **Critical Tool Blocking Issue**: Resolved Claude Code field name mismatch that caused tools to be incorrectly blocked even when permitted
- **JSON Output Format**: Ensured full compliance with Claude Code hook schema requirements
- **Error Handling**: Graceful degradation for invalid JSON inputs while maintaining hook functionality
- Ensured CLI hooks emit minimal JSON (`{"continue": true}`) while telemetry stays on stderr.

### Security
- **Enhanced PreToolUse Security**: Added pattern matching for dangerous commands (`rm -rf`, `shutdown`, etc.)
- **Sensitive File Protection**: Automatic detection and blocking of operations on `.env`, key files, and credentials
- **Package Installation Guards**: Human confirmation required for `npm install`, `pip install`, and similar operations

### Removed
- **Non-Official Event Support**: Removed Error event implementation to comply with Claude Code official specification (9 events only)

---

## [0.1.0] - 2025-09-18
### Added
- **Notification sounds**: play audio cues for user prompts/notifications
- **Task completion sounds**: dedicated audio for tool/task completion
- **Subagent completion sounds**: separate audio for subagent success
- **Smart throttling**: timestamp-based cache to avoid audio spam
- **Local audio files**: operate purely on local `.wav` assets, no API keys required
- **Cross-platform support**: macOS (afplay), Linux (ffplay/aplay), Windows (winsound)
- **Volume control**: macOS/Linux via player args, Windows via in-memory processing
- **Configuration system**: `.claude/hooks/utils/audio_config.json` manages volume, paths, mappings
- **Testing framework**: `uv run` + `pytest` scripts with `AUDIO_PLAYER_CMD` override

### Audio
- Default sound mappings: `task_complete.wav` (Stop), `agent_complete.wav` (SubagentStop), `user_prompt.wav` (Notification)
- Throttle windows: Stop/SubagentStop (120s), Notification (30s)
- Default volume: 0.2 (20%)

### Platform Support
- **Windows**: Python stdlib `winsound` + `audioop` for volume scaling
- **macOS**: `afplay` CLI with `-v` volume parameter
- **Linux**: supports `ffplay` (`-volume`) and `aplay`

[0.1.0]: https://github.com/kogitore/claude-code-hooks-herald
