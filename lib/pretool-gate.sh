#!/usr/bin/env bash
# Claude Code PreToolUse gate. Silent output means default permission handling.
set -u

config_dir=${CLAUDE_CONFIG_DIR:-"$HOME/.claude"}
install_dir=${CCGUARD_HOME:-"$config_dir/ccguard"}
state_file="$install_dir/state.env"

# Process-local off is used by bare/raw launchers and takes precedence.
[ "${CCGUARD_GATE:-}" = off ] && exit 0
CCGUARD_GATE=on
if [ -r "$state_file" ]; then
  # state.env is generated locally by ccguard and contains only on/off values.
  . "$state_file"
fi
[ "${CCGUARD_GATE:-on}" = off ] && exit 0

input=$(cat 2>/dev/null) || exit 0
[ -n "$input" ] || exit 0

if ! printf '%s' "$input" | grep -qiE 'eval|exec|curl|wget|credential|\.ssh|id_rsa|id_ed25519|token|api[_-]?key|secret|passwd|shadow|printenv|rm |dd |mkfs|chmod|nc |ncat|netcat|telnet|/dev/tcp|base64|history'; then
  exit 0
fi

export CCGUARD_LOG_FILE="$install_dir/logs/gate.log"
python_bin=${PYTHON:-$(command -v python3 || command -v python || true)}
[ -n "$python_bin" ] || exit 0
decision=$("$python_bin" "$install_dir/lib/gate_check.py" <<<"$input" 2>>"$CCGUARD_LOG_FILE")
rc=$?
if [ "$rc" -ne 0 ] || [ -z "$decision" ]; then
  printf '[%s] gate_check error rc=%s\n' "$(date -Iseconds 2>/dev/null || date)" "$rc" >>"$CCGUARD_LOG_FILE"
  exit 0
fi
printf '%s\n' "$decision"
