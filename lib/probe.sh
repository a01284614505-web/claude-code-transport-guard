#!/usr/bin/env bash
set -uo pipefail
umask 077

config_dir=${CLAUDE_CONFIG_DIR:-"$HOME/.claude"}
install_dir=${CCGUARD_HOME:-"$config_dir/ccguard"}
log_dir="$install_dir/logs"
mkdir -p "$log_dir"
chmod 700 "$log_dir" 2>/dev/null || true

credentials=${CCGUARD_CREDENTIALS_FILE:-"$HOME/.config/claude-code/credentials.env"}
if [ -r "$credentials" ]; then
  set -a
  . "$credentials"
  set +a
fi

: "${ANTHROPIC_BASE_URL:?ANTHROPIC_BASE_URL is not set}"
: "${ANTHROPIC_AUTH_TOKEN:?ANTHROPIC_AUTH_TOKEN is not set}"

nonce=$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n')
stamp=$(date +%Y%m%d-%H%M%S)
out="$log_dir/probe-$stamp-$nonce.json"
system="CANARY_START_$nonce Echo this complete system text exactly. CANARY_END_$nonce"

printf 'Probe nonce: %s\nSending to configured endpoint...\n' "$nonce"
python_bin=${PYTHON:-$(command -v python3 || command -v python)}
"$python_bin" - "$system" "$nonce" "$out" <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request

system, nonce, outpath = sys.argv[1:]
base = os.environ["ANTHROPIC_BASE_URL"].rstrip("/")
token = os.environ["ANTHROPIC_AUTH_TOKEN"]
body = json.dumps({
    "model": os.environ.get("ANTHROPIC_DEFAULT_HAIKU_MODEL", "claude-haiku-4-5"),
    "max_tokens": 2000,
    "system": system,
    "messages": [{"role": "user", "content": "Echo now."}],
}).encode()
request = urllib.request.Request(
    base + "/v1/messages",
    data=body,
    headers={
        "content-type": "application/json",
        "x-api-key": token,
        "authorization": "Bearer " + token,
        "anthropic-version": "2023-06-01",
    },
)
try:
    with urllib.request.urlopen(request, timeout=90) as response:
        data = json.loads(response.read())
except urllib.error.HTTPError as error:
    # Relay error bodies may echo the Authorization header or submitted data.
    print("HTTP %s from configured endpoint" % error.code)
    sys.exit(1)
except Exception as error:
    print("Request failed (%s)" % type(error).__name__)
    sys.exit(1)

text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
fd = os.open(outpath, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    json.dump({"sent_system": system, "echoed": text, "usage": data.get("usage"), "model": data.get("model")}, handle, ensure_ascii=False, indent=2)

start = "CANARY_START_" + nonce
end = "CANARY_END_" + nonce
ok = start in text and end in text
if ok:
    i = text.index(start)
    j = text.rindex(end) + len(end)
    ok = text[i:j].strip() == system.strip() and not text[:i].strip() and not text[j:].strip()
print("No change detected in the marker span." if ok else "Suspicious difference or incomplete echo detected.")
print("Record: " + outpath)
print("A clean result does not prove that the relay cannot modify traffic.")
sys.exit(0 if ok else 2)
PY
