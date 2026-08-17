#!/usr/bin/env bash

ccguard_load_config() {
  local config_dir=${CLAUDE_CONFIG_DIR:-"$HOME/.claude"}
  local install_dir=${CCGUARD_HOME:-"$config_dir/ccguard"}
  if [ -r "$install_dir/config.env" ]; then
    . "$install_dir/config.env"
  fi
}

ccguard_load_config

ccguard_load_credentials() {
  local credentials=${CCGUARD_CREDENTIALS_FILE:-"$HOME/.config/claude-code/credentials.env"}
  if [ -r "$credentials" ]; then
    set -a
    # This is the user's existing local environment file.
    . "$credentials"
    set +a
  fi
}

ccguard_find_claude() {
  if [ -n "${CCGUARD_CLAUDE_BIN:-}" ]; then
    printf '%s\n' "$CCGUARD_CLAUDE_BIN"
    return
  fi
  if [ -n "${CCGUARD_ORIGINAL_CLAUDE_BIN:-}" ] && [ -x "$CCGUARD_ORIGINAL_CLAUDE_BIN" ]; then
    printf '%s\n' "$CCGUARD_ORIGINAL_CLAUDE_BIN"
    return
  fi
  command -v claude 2>/dev/null || {
    printf 'ccguard: Claude Code executable not found; set CCGUARD_CLAUDE_BIN\n' >&2
    return 1
  }
}

ccguard_exec() {
  local binary=$1
  shift
  if [ -n "${CCGUARD_RUNNER:-}" ]; then
    exec "$CCGUARD_RUNNER" "$binary" "$@"
  fi
  exec "$binary" "$@"
}
