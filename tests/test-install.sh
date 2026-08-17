#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
export HOME="$TMP/home"
export CLAUDE_CONFIG_DIR="$HOME/.claude"
export XDG_BIN_HOME="$HOME/bin"
mkdir -p "$CLAUDE_CONFIG_DIR" "$XDG_BIN_HOME"

cat >"$CLAUDE_CONFIG_DIR/settings.json" <<'JSON'
{
  "model": "keep-me",
  "hooks": {
    "Stop": [
      {"hooks": [{"type": "command", "command": "/keep/stop"}]}
    ]
  }
}
JSON
cp "$CLAUDE_CONFIG_DIR/settings.json" "$TMP/settings.original"
cp "$ROOT/tests/fake-claude.sh" "$XDG_BIN_HOME/claude"
sed -i "1s|^#!/usr/bin/env bash$|#!$(command -v bash)|" "$XDG_BIN_HOME/claude"
chmod 700 "$XDG_BIN_HOME/claude"
export PATH="$XDG_BIN_HOME:$PATH"

bash "$ROOT/install.sh" >/dev/null
bash "$ROOT/install.sh" >/dev/null

status=$($XDG_BIN_HOME/ccguard status)
printf '%s' "$status" | grep -q 'prompt:  on'
printf '%s' "$status" | grep -q 'gate:    on'
python3 - "$CLAUDE_CONFIG_DIR/settings.json" <<'PY'
import json, sys
with open(sys.argv[1]) as handle:
    data = json.load(handle)
assert data["model"] == "keep-me"
assert len(data["hooks"]["PreToolUse"]) == 1
assert len(data["hooks"]["UserPromptSubmit"]) == 1
assert len(data["hooks"]["Stop"]) == 1
PY

guarded=$($XDG_BIN_HOME/claude-guarded --version 2>/dev/null)
bare=$($XDG_BIN_HOME/claude-bare --version 2>/dev/null)
raw=$($XDG_BIN_HOME/claude-raw --version 2>/dev/null)
printf '%s' "$guarded" | grep -q 'CCGUARD_PROMPT=on'
printf '%s' "$guarded" | grep -q -- '--append-system-prompt-file'
printf '%s' "$bare" | grep -q 'CCGUARD_PROMPT=off'
printf '%s' "$bare" | grep -q 'bare-system.txt'
printf '%s' "$raw" | grep -q 'CCGUARD_GATE=off'
printf '%s' "$raw" | grep -q 'empty-system.txt'
[ ! -s "$CLAUDE_CONFIG_DIR/ccguard/prompts/empty-system.txt" ]

$XDG_BIN_HOME/ccguard disable >/dev/null
status=$($XDG_BIN_HOME/ccguard status)
printf '%s' "$status" | grep -q 'prompt:  off'
$XDG_BIN_HOME/ccguard enable >/dev/null
$XDG_BIN_HOME/claude-probe help | grep -q 'Only the explicit run'

$XDG_BIN_HOME/ccguard uninstall >/dev/null
python3 - "$CLAUDE_CONFIG_DIR/settings.json" "$TMP/settings.original" <<'PY'
import json
import sys
with open(sys.argv[1]) as current, open(sys.argv[2]) as original:
    assert json.load(current) == json.load(original)
PY
[ -x "$XDG_BIN_HOME/claude" ]
[ ! -e "$XDG_BIN_HOME/ccguard" ]
[ ! -e "$CLAUDE_CONFIG_DIR/ccguard" ]

# Optional shim remains reversible across repeated installs.
cp "$XDG_BIN_HOME/claude" "$TMP/claude.original"
bash "$ROOT/install.sh" --with-claude-shim >/dev/null
[ -L "$XDG_BIN_HOME/claude" ]
bash "$ROOT/install.sh" --with-claude-shim >/dev/null
$XDG_BIN_HOME/ccguard uninstall --restore-backup >/dev/null
[ ! -L "$XDG_BIN_HOME/claude" ]
cmp "$XDG_BIN_HOME/claude" "$TMP/claude.original"

printf 'install lifecycle: ok\n'
