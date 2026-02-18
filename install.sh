#!/usr/bin/env bash
# Herald — one-step installer
# Usage: curl -fsSL <raw-url>/install.sh | bash
#    or: bash install.sh [target-dir]

set -euo pipefail

REPO_URL="https://github.com/user/herald-hooks.git"
DEFAULT_TARGET="$HOME/.herald"

# --- Helpers ----------------------------------------------------------------

info()  { printf '\033[1;34m[Herald]\033[0m %s\n' "$1"; }
ok()    { printf '\033[1;32m[Herald]\033[0m %s\n' "$1"; }
warn()  { printf '\033[1;33m[Herald]\033[0m %s\n' "$1"; }
fail()  { printf '\033[1;31m[Herald]\033[0m %s\n' "$1" >&2; exit 1; }

check_cmd() {
  command -v "$1" >/dev/null 2>&1
}

# --- Pre-flight checks ------------------------------------------------------

info "Checking prerequisites..."

if ! check_cmd git; then
  fail "git is required but not found. Install it first."
fi

if ! check_cmd bun; then
  warn "Bun not found. Installing Bun..."
  curl -fsSL https://bun.sh/install | bash
  export PATH="$HOME/.bun/bin:$PATH"
  if ! check_cmd bun; then
    fail "Bun installation failed. Visit https://bun.sh for manual install."
  fi
  ok "Bun installed."
fi

# --- Clone / Update ----------------------------------------------------------

TARGET="${1:-$DEFAULT_TARGET}"

if [ -d "$TARGET/.git" ]; then
  info "Existing installation found at $TARGET — pulling latest..."
  git -C "$TARGET" pull --ff-only || warn "Pull failed — using existing version."
else
  info "Cloning Herald to $TARGET..."
  git clone "$REPO_URL" "$TARGET"
fi

# --- Ensure sounds directory -------------------------------------------------

SOUNDS_DIR="$TARGET/.claude/sounds"
if [ ! -d "$SOUNDS_DIR" ]; then
  mkdir -p "$SOUNDS_DIR"
  info "Created $SOUNDS_DIR — add your .wav files there."
else
  info "Sounds directory exists."
fi

# --- Merge settings.json ----------------------------------------------------

HERALD_SETTINGS="$TARGET/.claude/settings.json"
info "Herald settings located at: $HERALD_SETTINGS"
info ""
info "To integrate with your project, copy or merge the hooks config:"
info "  cp $HERALD_SETTINGS /path/to/your/project/.claude/settings.json"
info ""
info "Or merge the \"hooks\" key into your existing .claude/settings.json."

# --- Verify ------------------------------------------------------------------

info "Running quick verification..."
RESULT=$(echo '{"message":"install-test"}' | bun run "$TARGET/.claude/hooks/herald.ts" --hook Notification 2>/dev/null || true)

if echo "$RESULT" | grep -q '"continue"'; then
  ok "Verification passed."
else
  warn "Verification returned unexpected output. Check your setup manually."
fi

# --- Done --------------------------------------------------------------------

echo ""
ok "Herald installed at: $TARGET"
echo ""
info "Next steps:"
info "  1. Add .wav files to $SOUNDS_DIR"
info "  2. Copy settings to your project:"
info "     cp $HERALD_SETTINGS <your-project>/.claude/settings.json"
info "  3. Start Claude Code — Herald will handle all hook events."
echo ""
