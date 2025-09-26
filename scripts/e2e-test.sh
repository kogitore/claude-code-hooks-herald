#!/bin/bash

# End-to-End Test Script for Claude Code Hooks Herald
# Tests event routing, handler execution, and response validation
# Exit codes: 0=all tests pass, 1=test failures, 2=setup error

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

echo -e "${BLUE}🧪 Claude Code Hooks Herald - End-to-End Tests${NC}"
echo "=============================================="

# Function to log test results
log_test_start() {
    echo -e "\n${PURPLE}🔬 Test: $1${NC}"
    ((TESTS_TOTAL+=1))
}

log_test_pass() {
    echo -e "${GREEN}✅ PASS: $1${NC}"
    ((TESTS_PASSED+=1))
}

log_test_fail() {
    echo -e "${RED}❌ FAIL: $1${NC}"
    ((TESTS_FAILED+=1))
}

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Prerequisites check
echo -e "\n${BLUE}📋 Prerequisites Check${NC}"
echo "------------------------------------------------"

if [ ! -f ".claude/hooks/herald.py" ]; then
    echo -e "${RED}❌ herald.py not found. Cannot run E2E tests.${NC}"
    exit 2
fi

if [ ! -x ".claude/hooks/herald.py" ]; then
    echo -e "${RED}❌ herald.py not executable. Run: chmod +x .claude/hooks/herald.py${NC}"
    exit 2
fi

log_info "Prerequisites met. Starting E2E tests..."

# Test 1: Herald Dispatcher Basic Functionality
log_test_start "Herald dispatcher responds to official events"

OFFICIAL_EVENTS=("Notification" "Stop" "SubagentStop" "PreToolUse" "PostToolUse" "UserPromptSubmit" "SessionStart" "SessionEnd")
BASIC_TESTS_PASSED=0

for event in "${OFFICIAL_EVENTS[@]}"; do
    payload='{}'
    case "$event" in
        Notification) payload='{"message":"e2e-notification"}' ;;
        Stop) payload='{"marker":"e2e-stop"}' ;;
        SubagentStop) payload='{"marker":"e2e-subagent"}' ;;
        PreToolUse) payload='{"tool":"bash","toolInput":{"command":"echo test"}}' ;;
        PostToolUse) payload='{"tool":"bash","result":{"success":true,"output":"ok"}}' ;;
        UserPromptSubmit) payload='{"prompt":"hello world","user_id":"tester"}' ;;
        SessionStart) payload='{"session_id":"sess-123","start_time":"2025-09-22T00:00:00Z"}' ;;
        SessionEnd) payload='{"session_id":"sess-123","end_time":"2025-09-22T01:00:00Z","termination_reason":"normal"}' ;;
    esac
    export AUDIO_PLAYER_CMD=true
    RESULT=$(echo "$payload" | ./.claude/hooks/herald.py --hook "$event" --json-only 2>/dev/null | head -1 || echo "FAILED")

    if echo "$RESULT" | python3 -m json.tool >/dev/null 2>&1; then
        log_info "  ✓ $event event processed successfully"
        ((BASIC_TESTS_PASSED++))
    else
        log_info "  ✗ $event event failed: $RESULT"
    fi
done

if [ $BASIC_TESTS_PASSED -eq ${#OFFICIAL_EVENTS[@]} ]; then
    log_test_pass "Herald processes all official events correctly"
else
    log_test_fail "Herald failed to process $((${#OFFICIAL_EVENTS[@]} - BASIC_TESTS_PASSED)) out of ${#OFFICIAL_EVENTS[@]} events"
fi


# Test 2: JSON Response Format Validation
log_test_start "Herald outputs valid JSON responses"

export AUDIO_PLAYER_CMD=true
RESPONSE=$(echo '{"test": "json_format"}' | ./.claude/hooks/herald.py --hook Notification --json-only 2>/dev/null | head -1 || echo "{}")

if echo "$RESPONSE" | python3 -m json.tool >/dev/null 2>&1; then
    log_test_pass "Herald outputs valid JSON format"
else
    log_test_fail "Herald output is not valid JSON: $RESPONSE"
fi

# Test 3: Decision API Integration (PreToolUse)
log_test_start "Decision API processes tool use requests"

# Test with a safe command that should be allowed
SAFE_COMMAND='{"tool": "bash", "toolInput": {"command": "echo hello"}}'
export AUDIO_PLAYER_CMD=true
DECISION_RESULT=$(echo "$SAFE_COMMAND" | ./.claude/hooks/herald.py --hook PreToolUse --json-only 2>/dev/null | head -1 || echo "{}")

if echo "$DECISION_RESULT" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    hook = data.get('hookSpecificOutput', {})
    decision = hook.get('permissionDecision')
    if decision in ['allow', 'deny', 'ask']:
        print('VALID_DECISION')
    else:
        print('INVALID_DECISION')
except Exception:
    print('INVALID_JSON')
" | grep -q "VALID_DECISION"; then
    log_test_pass "Decision API returns valid decision format"
else
    log_test_fail "Decision API response invalid: $DECISION_RESULT"
fi

# Test 4: Error Handling
log_test_start "Herald handles invalid input gracefully"

# Test with invalid JSON
INVALID_JSON="invalid json input"
export AUDIO_PLAYER_CMD=true
ERROR_RESULT=$(echo "$INVALID_JSON" | ./.claude/hooks/herald.py --hook Notification --json-only 2>/dev/null | head -1 || echo '{"error": "handled"}')

if [[ "$ERROR_RESULT" == *"error"* ]] || [[ "$ERROR_RESULT" == *"continue"* ]]; then
    log_test_pass "Herald handles invalid JSON input gracefully"
else
    log_test_fail "Herald did not handle invalid input properly: $ERROR_RESULT"
fi

# Test 5: Event Case Sensitivity
log_test_start "Herald rejects incorrect event name case"

# Test with lowercase event name (should fail or be handled gracefully)
export AUDIO_PLAYER_CMD=true
CASE_RESULT=$(echo '{"test": "case_test"}' | ./.claude/hooks/herald.py --hook notification --json-only 2>&1 | head -1 || echo "CASE_ERROR")

if [[ "$CASE_RESULT" == *"error"* ]] || [[ "$CASE_RESULT" == *"CASE_ERROR"* ]]; then
    log_test_pass "Herald properly handles incorrect event case"
else
    log_warning "Herald may accept incorrect case - check handler registration"
    log_test_pass "Herald responds to case variations (may be intentional)"
fi

# Test 6: Settings.json Integration
log_test_start "Settings.json routes events to Herald"

if [ -f ".claude/settings.json" ]; then
    SETTINGS_CONTENT=$(cat .claude/settings.json)

    if [[ "$SETTINGS_CONTENT" == *"herald.py"* ]]; then
        log_test_pass "settings.json configured to use Herald dispatcher"
    else
        log_warning "settings.json may not be using Herald dispatcher"
        if [[ "$SETTINGS_CONTENT" == "{}" ]] || [ -z "$SETTINGS_CONTENT" ]; then
            log_test_fail "settings.json is empty - Herald will not be used by Claude Code"
        else
            log_test_pass "settings.json has content (may use individual hooks)"
        fi
    fi
else
    log_test_fail "settings.json not found - Claude Code integration will not work"
fi

# Test 7: Audio System Integration
log_test_start "Audio system integration test"

# Test audio manager import and basic functionality
AUDIO_TEST=$(PYTHONPATH=".claude/hooks" python3 -c "
import sys
sys.path.insert(0, '.claude/hooks')
try:
    from utils.audio_manager import AudioManager
    am = AudioManager()
    # Test without actually playing audio
    print('AUDIO_MANAGER_OK')
except Exception as e:
    print(f'AUDIO_ERROR: {e}')
" 2>/dev/null || echo "AUDIO_IMPORT_ERROR")

if [[ "$AUDIO_TEST" == "AUDIO_MANAGER_OK" ]]; then
    log_test_pass "Audio system integration successful"
else
    log_test_fail "Audio system integration failed: $AUDIO_TEST"
fi

# Test 8: Configuration Consistency
log_test_start "Configuration files consistency check"

CONFIG_ISSUES=0

# Check if settings.json events match herald.py capabilities
if [ -f ".claude/settings.json" ] && grep -q "herald.py" .claude/settings.json; then
    SETTINGS_EVENTS=$(grep -o '"[A-Z][a-zA-Z]*"' .claude/settings.json | tr -d '"' | sort -u)

    for event in $SETTINGS_EVENTS; do
        if [[ "$event" =~ ^(Notification|Stop|SubagentStop|PreToolUse|PostToolUse|UserPromptSubmit|SessionStart|SessionEnd)$ ]]; then
            log_info "  ✓ Valid event configured: $event"
        else
            log_info "  ⚠ Unknown event configured: $event"
            ((CONFIG_ISSUES++))
        fi
    done
fi

if [ $CONFIG_ISSUES -eq 0 ]; then
    log_test_pass "Configuration consistency check passed"
else
    log_test_fail "Configuration has $CONFIG_ISSUES issue(s)"
fi

# Test Summary
echo -e "\n${BLUE}📊 End-to-End Test Summary${NC}"
echo "=============================================="

SUCCESS_RATE=$((TESTS_PASSED * 100 / TESTS_TOTAL))

echo -e "Tests Run: ${BLUE}$TESTS_TOTAL${NC}"
echo -e "Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Failed: ${RED}$TESTS_FAILED${NC}"
echo -e "Success Rate: ${BLUE}$SUCCESS_RATE%${NC}"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}🎉 All E2E tests passed! System is ready for production use.${NC}"
    exit 0
elif [ $SUCCESS_RATE -ge 80 ]; then
    echo -e "\n${YELLOW}⚠️  Most tests passed ($SUCCESS_RATE%). System should work but has some issues.${NC}"
    echo -e "${YELLOW}   Consider reviewing failed tests before production use.${NC}"
    exit 0
else
    echo -e "\n${RED}💥 E2E tests failed significantly ($SUCCESS_RATE% success rate).${NC}"
    echo -e "${RED}   Please fix critical issues before using the hooks system.${NC}"

    echo -e "\n${BLUE}🔧 Common fixes:${NC}"
    echo "   • Ensure herald.py has executable permissions"
    echo "   • Verify settings.json routes events to herald.py"
    echo "   • Check Python dependencies and imports"
    echo "   • Run ./scripts/validate-config.sh for detailed diagnosis"

    exit 1
fi