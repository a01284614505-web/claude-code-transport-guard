#!/usr/bin/env bash
# Linux simulation of Termux-style PREFIX/shebang layout; not an Android run.
set -euo pipefail
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT
export HOME="$TEST_DIR/home"
export PREFIX="$TEST_DIR/termux-prefix"
export CLAUDE_CONFIG_DIR="$HOME/.claude"
export XDG_BIN_HOME="$HOME/bin"
mkdir -p "$PREFIX/bin" "$XDG_BIN_HOME"
ln -s "$(command -v bash)" "$PREFIX/bin/bash"
export BASH="$PREFIX/bin/bash"
export PYTHON="$(command -v python3)"
cp "$ROOT/tests/fake-claude.sh" "$XDG_BIN_HOME/claude"
chmod 700 "$XDG_BIN_HOME/claude"
export PATH="$XDG_BIN_HOME:$PATH"
"$PREFIX/bin/bash" "$ROOT/install.sh" >/dev/null
first_line=$(head -n 1 "$CLAUDE_CONFIG_DIR/ccguard/lib/pretool-gate.sh")
[ "$first_line" = "#!$BASH" ]
first_line=$(head -n 1 "$XDG_BIN_HOME/ccguard")
[ "$first_line" = "#!$BASH" ]
"$XDG_BIN_HOME/ccguard" status >/dev/null
"$XDG_BIN_HOME/ccguard" uninstall >/dev/null
printf 'Termux-style layout simulation: ok (actual Android not tested)\n'
