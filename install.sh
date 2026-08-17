#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
config_dir=${CLAUDE_CONFIG_DIR:-"$HOME/.claude"}
install_dir=${CCGUARD_HOME:-"$config_dir/ccguard"}
bin_dir=${XDG_BIN_HOME:-"$HOME/.local/bin"}
settings="$config_dir/settings.json"
with_shim=0

usage() {
  cat <<'EOF'
Usage: ./install.sh [--with-claude-shim]

Installs ccguard- and mode-specific commands without changing the existing
claude command. --with-claude-shim additionally creates claude -> claude-guarded
after saving an existing claude file in the install manifest.
EOF
}
while [ "$#" -gt 0 ]; do
  case "$1" in
    --with-claude-shim) with_shim=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
  shift
done

python_bin=${PYTHON:-$(command -v python3 || command -v python || true)}
bash_bin=${BASH:-$(command -v bash || true)}
[ -n "$python_bin" ] || { printf 'Python 3 is required\n' >&2; exit 1; }
[ -n "$bash_bin" ] || { printf 'Bash is required\n' >&2; exit 1; }
mkdir -p "$bin_dir" "$config_dir" "$install_dir/logs"
umask 077
chmod 700 "$install_dir" "$install_dir/logs"

stamp=$(date +%Y%m%d-%H%M%S)
previous_original=""
previous_settings_backup=""
previous_claude_backup=""
if [ -r "$install_dir/config.env" ]; then
  . "$install_dir/config.env"
  previous_original=${CCGUARD_ORIGINAL_CLAUDE_BIN:-}
fi
if [ -r "$install_dir/manifest.env" ]; then
  . "$install_dir/manifest.env"
  previous_settings_backup=${SETTINGS_BACKUP:-}
  previous_claude_backup=${CLAUDE_BACKUP:-}
fi
original_claude=${previous_original:-$(command -v claude 2>/dev/null || true)}
settings_backup=${previous_settings_backup:-"$install_dir/backups/settings.$stamp.json"}
claude_backup=${previous_claude_backup:-"$install_dir/backups/claude.$stamp"}
mkdir -p "$install_dir/backups"
if [ -z "$previous_settings_backup" ] && [ -f "$settings" ]; then
  cp "$settings" "$settings_backup"
fi
if [ -z "$previous_claude_backup" ] && [ -e "$bin_dir/claude" ] && [ ! -L "$bin_dir/claude" ]; then
  cp "$bin_dir/claude" "$claude_backup"
fi

cp -R "$ROOT/lib" "$install_dir/"
cp -R "$ROOT/prompts" "$install_dir/"
chmod 700 "$install_dir/lib"/*.sh "$install_dir/lib"/*.py
chmod 600 "$install_dir/prompts"/*

cat >"$install_dir/config.env" <<EOF
CCGUARD_HOME=$install_dir
CCGUARD_ORIGINAL_CLAUDE_BIN=$original_claude
EOF
cat >"$install_dir/manifest.env" <<EOF
SETTINGS_BACKUP=$settings_backup
CLAUDE_BACKUP=$claude_backup
EOF
chmod 600 "$install_dir/config.env" "$install_dir/manifest.env"

"$python_bin" "$install_dir/lib/settings.py" install "$settings" "$install_dir"
printf 'CCGUARD_PROMPT=on\nCCGUARD_GATE=on\n' >"$install_dir/state.env"
chmod 600 "$install_dir/state.env"

for name in ccguard claude-guarded claude-bare claude-raw claude-probe; do
  cp "$ROOT/bin/$name" "$bin_dir/$name"
  chmod 700 "$bin_dir/$name"
done
# Termux may not provide /usr/bin/env; adapt installed Bash entrypoints.
for file in "$install_dir"/lib/*.sh "$bin_dir"/ccguard "$bin_dir"/claude-guarded "$bin_dir"/claude-bare "$bin_dir"/claude-raw "$bin_dir"/claude-probe; do
  [ -f "$file" ] || continue
  sed -i "1s|^#!/usr/bin/env bash$|#!$bash_bin|" "$file"
done
if [ "$with_shim" -eq 1 ]; then
  rm -f "$bin_dir/claude"
  ln -s "$bin_dir/claude-guarded" "$bin_dir/claude"
fi

printf 'Installed ccguard at %s\n' "$install_dir"
printf 'Commands:\n  %s\n  %s\n  %s\n  %s\n' \
  "$bin_dir/ccguard status" "$bin_dir/claude-guarded" "$bin_dir/claude-bare" "$bin_dir/claude-raw"
if [ "$with_shim" -eq 1 ]; then
  printf 'Created claude -> claude-guarded shim\n'
fi
