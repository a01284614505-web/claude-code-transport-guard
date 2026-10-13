#!/usr/bin/env bash
# Claude Code PreToolUse gate. The Python checker is the only rule engine.
set -u

config_dir=${CLAUDE_CONFIG_DIR:-"$HOME/.claude"}
install_dir=${CCGUARD_HOME:-"$config_dir/ccguard"}
state_file="$install_dir/state.env"

# Process-local off is used by bare/raw launchers and takes precedence.
[ "${CCGUARD_GATE:-}" = off ] && exit 0
if [ -r "$state_file" ]; then
  # Never execute the state file as shell code.
  grep -qx 'CCGUARD_GATE=off' "$state_file" && exit 0
fi
export CCGUARD_LOG_FILE="$install_dir/logs/gate.log"
python_bin=${PYTHON:-$(command -v python3 || command -v python || true)}
if [ -z "$python_bin" ] || [ ! -r "$install_dir/lib/gate_check.py" ]; then
  printf 'ccguard: checker unavailable; Bash call blocked\n' >&2
  exit 2
fi
"$python_bin" "$install_dir/lib/gate_check.py"
rc=$?
if [ "$rc" -ne 0 ]; then
  [ "$rc" -eq 2 ] && exit 2
  printf 'ccguard: checker failed; Bash call blocked\n' >&2
  exit 2
fi
