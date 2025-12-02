#!/bin/bash

# Health Check Script for Claude Code Hooks Herald
# Validates system dependencies, Python imports, and herald functionality
# Exit codes: 0=healthy, 1=dependency error, 2=import error, 3=herald error

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
ERRORS=0
WARNINGS=0

echo -e "${BLUE}🏥 Claude Code Hooks Herald - Health Check${NC}"
echo "========================================="

# Function to log errors
log_error() {
    echo -e "${RED}❌ ERROR: $1${NC}"
    ((ERRORS++))
}

# Function to log warnings
log_warning() {
    echo -e "${YELLOW}⚠️  WARNING: $1${NC}"
    ((WARNINGS++))
}

# Function to log success
log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Function to log info
log_info() {
    echo -e "${BLUE}ℹ️  INFO: $1${NC}"
}

echo -e "\n${BLUE}🎵 Step 1: Audio Player Detection${NC}"
echo "------------------------------------------------"

# Check for audio players
AUDIO_PLAYERS=()

# macOS - afplay
if command -v afplay >/dev/null 2>&1; then
    AUDIO_PLAYERS+=("afplay (macOS)")
    log_success "afplay detected (macOS native)"
fi

# Linux/Cross-platform - ffplay
if command -v ffplay >/dev/null 2>&1; then
    AUDIO_PLAYERS+=("ffplay (FFmpeg)")
    log_success "ffplay detected (FFmpeg)"
fi

# Linux - aplay
if command -v aplay >/dev/null 2>&1; then
    AUDIO_PLAYERS+=("aplay (ALSA)")
    log_success "aplay detected (ALSA)"
fi

# Windows/Cross-platform - Python winsound (check if available)
if python3 -c "import winsound" 2>/dev/null; then
    AUDIO_PLAYERS+=("winsound (Python)")
    log_success "winsound module available (Python)"
fi

if [ ${#AUDIO_PLAYERS[@]} -eq 0 ]; then
    log_error "No audio players detected"
    echo "         Supported: afplay (macOS), ffplay (FFmpeg), aplay (ALSA), winsound (Python)"
else
    log_success "Audio players available: $(IFS=', '; echo "${AUDIO_PLAYERS[*]}")"
fi

# Test environment override
if [ -n "$AUDIO_PLAYER_CMD" ]; then
    log_info "AUDIO_PLAYER_CMD override set: $AUDIO_PLAYER_CMD"
fi

echo -e "\n${BLUE}🐍 Step 2: Python Environment Check${NC}"
echo "------------------------------------------------"

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
log_success "Python version: $PYTHON_VERSION"

# Check if we're in project directory
if [ ! -f ".claude/hooks/herald.py" ]; then
    log_error "Not in project root directory (herald.py not found)"
    log_info "Run this script from the project root directory"
else
    log_success "Project root directory detected"
fi

# Test Python imports
echo -e "\n${BLUE}📦 Step 3: Python Dependencies Check${NC}"
echo "------------------------------------------------"

PYTHON_IMPORTS=(
    "json:JSON processing"
    "sys:System interface"
    "os:Operating system interface"
    "subprocess:Process management"
    "argparse:Argument parsing"
    "pathlib:Path handling"
)

for import_spec in "${PYTHON_IMPORTS[@]}"; do
    module=$(echo "$import_spec" | cut -d':' -f1)
    description=$(echo "$import_spec" | cut -d':' -f2)

    if python3 -c "import $module" 2>/dev/null; then
        log_success "$module ($description)"
    else
        log_error "Failed to import $module ($description)"
    fi
done

# Test project-specific imports
echo -e "\n${BLUE}🔧 Step 4: Herald Dependencies Check${NC}"
echo "------------------------------------------------"

# Test herald.py imports
if [ -f ".claude/hooks/herald.py" ]; then
    # Test basic herald import path setup
    PYTHONPATH=".claude/hooks" python3 -c "
import sys
sys.path.insert(0, '.claude/hooks')
try:
    from utils.base_hook import BaseHook
    print('BaseHook import: SUCCESS')
except ImportError as e:
    print(f'BaseHook import: FAILED - {e}')

try:
    from utils.audio_manager import AudioManager
    print('AudioManager import: SUCCESS')
except ImportError as e:
    print(f'AudioManager import: FAILED - {e}')

try:
    from utils.decision_api import DecisionAPI
    print('DecisionAPI import: SUCCESS')
except ImportError as e:
    print(f'DecisionAPI import: FAILED - {e}')
" 2>&1 | while read line; do
        if [[ $line == *"SUCCESS"* ]]; then
            log_success "$line"
        elif [[ $line == *"FAILED"* ]]; then
            log_error "$line"
        else
            log_info "$line"
        fi
    done
else
    log_error "herald.py not found - cannot test imports"
fi

echo -e "\n${BLUE}🧪 Step 5: Herald Dispatcher Test${NC}"
echo "------------------------------------------------"

# Test herald.py basic functionality
if [ -f ".claude/hooks/herald.py" ] && [ -x ".claude/hooks/herald.py" ]; then
    log_success "herald.py is executable"

    # Test herald help/version
    if ./.claude/hooks/herald.py --help >/dev/null 2>&1; then
        log_success "herald.py responds to --help"
    else
        log_warning "herald.py does not respond to --help properly"
    fi

    # Test herald basic event processing (dry run)
    echo -e "\n${YELLOW}Testing herald dispatcher with test events...${NC}"

    TEST_EVENTS=("Notification" "Stop" "SubagentStop")
    for event in "${TEST_EVENTS[@]}"; do
        # Use no-audio flag to avoid actual sound during health check
        if echo '{"test": "health_check"}' | AUDIO_PLAYER_CMD=true ./.claude/hooks/herald.py --hook "$event" --json-only >/dev/null 2>&1; then
            log_success "Herald processes $event events"
        else
            log_error "Herald failed to process $event events"
        fi
    done

else
    if [ ! -f ".claude/hooks/herald.py" ]; then
        log_error "herald.py not found"
    else
        log_error "herald.py not executable (run: chmod +x .claude/hooks/herald.py)"
    fi
fi

echo -e "\n${BLUE}⚙️  Step 6: Configuration Files Check${NC}"
echo "------------------------------------------------"

# Quick config file existence check
CONFIG_FILES=(
    ".claude/settings.json:Claude Code hook settings"
    ".claude/hooks/utils/audio_config.json:Audio configuration"
)

for config_spec in "${CONFIG_FILES[@]}"; do
    file=$(echo "$config_spec" | cut -d':' -f1)
    description=$(echo "$config_spec" | cut -d':' -f2)

    if [ -f "$file" ]; then
        log_success "$file exists ($description)"
    else
        log_warning "$file missing ($description)"
    fi
done

# Optional files
OPTIONAL_FILES=(
    ".claude/hooks/utils/decision_policy.json:Decision policy configuration"
)

for config_spec in "${OPTIONAL_FILES[@]}"; do
    file=$(echo "$config_spec" | cut -d':' -f1)
    description=$(echo "$config_spec" | cut -d':' -f2)

    if [ -f "$file" ]; then
        log_success "$file exists ($description)"
    else
        log_info "$file not present ($description) - using defaults"
    fi
done

echo -e "\n${BLUE}🔍 Step 7: Environment Variables${NC}"
echo "------------------------------------------------"

# Check relevant environment variables
ENV_VARS=(
    "CLAUDE_PROJECT_DIR"
    "CLAUDE_SOUNDS_DIR"
    "AUDIO_SOUNDS_DIR"
    "AUDIO_PLAYER_CMD"
)

for var in "${ENV_VARS[@]}"; do
    if [ -n "${!var}" ]; then
        log_info "$var = ${!var}"
    fi
done

if [ -z "$CLAUDE_PROJECT_DIR" ]; then
    log_info "CLAUDE_PROJECT_DIR not set (using current directory)"
fi

echo -e "\n${BLUE}📊 Health Check Summary${NC}"
echo "========================================="

if [ $ERRORS -eq 0 ]; then
    if [ $WARNINGS -eq 0 ]; then
        echo -e "${GREEN}💚 System is healthy! All dependencies available.${NC}"
        exit 0
    else
        echo -e "${YELLOW}💛 System mostly healthy with $WARNINGS warning(s).${NC}"
        echo -e "${YELLOW}   Basic functionality should work.${NC}"
        exit 0
    fi
else
    echo -e "${RED}💥 Health check failed with $ERRORS error(s) and $WARNINGS warning(s).${NC}"
    echo -e "${RED}   Please resolve errors before using the hooks system.${NC}"

    echo -e "\n${BLUE}🔧 Suggested fixes:${NC}"
    if [[ $ERRORS -gt 0 ]]; then
        echo "   • Run: chmod +x .claude/hooks/herald.py"
        echo "   • Install missing audio players (ffmpeg for ffplay)"
        echo "   • Check Python imports and dependencies"
        echo "   • Verify you're in the project root directory"
    fi

    exit 1
fi