#!/bin/bash

# Configuration Validation Script for Claude Code Hooks Herald
# Validates settings.json, herald.py permissions, and audio files
# Exit codes: 0=success, 1=configuration error, 2=permission error, 3=audio error

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

echo -e "${BLUE}🔍 Claude Code Hooks Herald - Configuration Validation${NC}"
echo "=================================================="

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

echo -e "\n${BLUE}📋 Step 1: Validating .claude/settings.json${NC}"
echo "------------------------------------------------"

# Check if settings.json exists
if [ ! -f ".claude/settings.json" ]; then
    log_error "settings.json not found at .claude/settings.json"
else
    log_success "settings.json exists"

    # Check if settings.json is empty or contains only {}
    CONTENT=$(cat .claude/settings.json | tr -d '[:space:]')
    if [ "$CONTENT" = "{}" ] || [ -z "$CONTENT" ]; then
        log_error "settings.json is empty or contains only '{}'"
        echo "         Herald dispatcher will not be used!"
    else
        log_success "settings.json has content"

        # Validate JSON format
        if ! python3 -m json.tool .claude/settings.json >/dev/null 2>&1; then
            log_error "settings.json contains invalid JSON syntax"
        else
            log_success "settings.json has valid JSON syntax"

            # Check for hooks configuration
            if grep -q '"hooks"' .claude/settings.json; then
                log_success "hooks configuration found"

                # Check for herald.py references
                if grep -q "herald.py" .claude/settings.json; then
                    log_success "herald.py dispatcher configured"

                    # Check event name case sensitivity
                    EVENTS=("Notification" "Stop" "SubagentStop")
                    for event in "${EVENTS[@]}"; do
                        if grep -q "\"$event\"" .claude/settings.json; then
                            log_success "Event '$event' properly capitalized"
                        else
                            # Check for lowercase versions
                            lowercase=$(echo "$event" | tr '[:upper:]' '[:lower:]')
                            if grep -q "\"$lowercase\"" .claude/settings.json; then
                                log_error "Event name '$lowercase' should be '$event' (case sensitive)"
                            else
                                log_warning "Event '$event' not configured in settings.json"
                            fi
                        fi
                    done
                else
                    log_warning "herald.py not referenced in settings.json"
                    echo "         Using individual hook files instead of dispatcher"
                fi
            else
                log_warning "No hooks configuration found in settings.json"
            fi
        fi
    fi
fi

echo -e "\n${BLUE}🛡️  Step 2: Validating herald.py permissions${NC}"
echo "------------------------------------------------"

# Check if herald.py exists
if [ ! -f ".claude/hooks/herald.py" ]; then
    log_error "herald.py not found at .claude/hooks/herald.py"
else
    log_success "herald.py exists"

    # Check executable permissions
    if [ -x ".claude/hooks/herald.py" ]; then
        log_success "herald.py has executable permissions"
    else
        log_error "herald.py is not executable (run: chmod +x .claude/hooks/herald.py)"
    fi

    # Check shebang
    if head -1 .claude/hooks/herald.py | grep -q "#!/"; then
        log_success "herald.py has proper shebang"
    else
        log_warning "herald.py missing shebang line"
    fi
fi

echo -e "\n${BLUE}🔊 Step 3: Validating audio configuration${NC}"
echo "------------------------------------------------"

# Check audio_config.json
if [ ! -f ".claude/hooks/utils/audio_config.json" ]; then
    log_error "audio_config.json not found at .claude/hooks/utils/audio_config.json"
else
    log_success "audio_config.json exists"

    # Validate JSON format
    if ! python3 -m json.tool .claude/hooks/utils/audio_config.json >/dev/null 2>&1; then
        log_error "audio_config.json contains invalid JSON syntax"
    else
        log_success "audio_config.json has valid JSON syntax"

        # Extract base_path from audio config
        BASE_PATH=$(python3 -c "
import json
with open('.claude/hooks/utils/audio_config.json') as f:
    config = json.load(f)
    print(config.get('sound_files', {}).get('base_path', './.claude/sounds'))
" 2>/dev/null || echo "./.claude/sounds")

        # Check if sounds directory exists
        if [ ! -d "$BASE_PATH" ]; then
            log_error "Audio directory '$BASE_PATH' does not exist"
        else
            log_success "Audio directory '$BASE_PATH' exists"

            # Check for required audio files
            AUDIO_FILES=("task_complete.wav" "agent_complete.wav" "user_prompt.wav")
            for file in "${AUDIO_FILES[@]}"; do
                if [ -f "$BASE_PATH/$file" ]; then
                    log_success "Audio file '$file' found"
                else
                    log_warning "Audio file '$file' missing from '$BASE_PATH'"
                fi
            done
        fi
    fi
fi

# Check environment variable overrides
if [ -n "$CLAUDE_SOUNDS_DIR" ]; then
    if [ -d "$CLAUDE_SOUNDS_DIR" ]; then
        log_success "CLAUDE_SOUNDS_DIR override: $CLAUDE_SOUNDS_DIR"
    else
        log_error "CLAUDE_SOUNDS_DIR points to non-existent directory: $CLAUDE_SOUNDS_DIR"
    fi
fi

if [ -n "$AUDIO_SOUNDS_DIR" ]; then
    if [ -d "$AUDIO_SOUNDS_DIR" ]; then
        log_success "AUDIO_SOUNDS_DIR override: $AUDIO_SOUNDS_DIR"
    else
        log_error "AUDIO_SOUNDS_DIR points to non-existent directory: $AUDIO_SOUNDS_DIR"
    fi
fi

echo -e "\n${BLUE}📝 Step 4: Validating decision policy${NC}"
echo "------------------------------------------------"

# Check decision_policy.json
if [ ! -f ".claude/hooks/utils/decision_policy.json" ]; then
    if [ -f ".claude/hooks/utils/decision_policy.example.json" ]; then
        log_warning "decision_policy.json not found, but example file exists"
        echo "         Consider copying example file and customizing it"
    else
        log_warning "No decision policy configuration found"
    fi
else
    log_success "decision_policy.json exists"

    # Validate JSON format
    if ! python3 -m json.tool .claude/hooks/utils/decision_policy.json >/dev/null 2>&1; then
        log_error "decision_policy.json contains invalid JSON syntax"
    else
        log_success "decision_policy.json has valid JSON syntax"
    fi
fi

echo -e "\n${BLUE}📊 Validation Summary${NC}"
echo "=================================================="

if [ $ERRORS -eq 0 ]; then
    if [ $WARNINGS -eq 0 ]; then
        echo -e "${GREEN}🎉 All validations passed! Configuration is ready.${NC}"
        exit 0
    else
        echo -e "${YELLOW}⚠️  Configuration valid with $WARNINGS warning(s).${NC}"
        echo -e "${YELLOW}   System should work but consider addressing warnings.${NC}"
        exit 0
    fi
else
    echo -e "${RED}💥 Configuration validation failed with $ERRORS error(s) and $WARNINGS warning(s).${NC}"
    echo -e "${RED}   Please fix errors before proceeding.${NC}"
    exit 1
fi