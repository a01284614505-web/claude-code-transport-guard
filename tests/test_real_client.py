#!/usr/bin/env python3
"""Exercise the installed PreToolUse hook with a real Claude Code CLI and a local fake API.

Requires --client pointing to Claude Code v2.1.295+. No real model, credentials,
network target, or destructive host command is involved.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import settings  # noqa: E402


def events(block, stop_reason):
    yield "message_start", {
        "type": "message_start", "message": {
            "id": "msg_local_test", "type": "message", "role": "assistant",
            "model": "claude-sonnet-5-5", "content": [], "stop_reason": None,
            "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 0},
        },
    }
    yield "content_block_start", {
        "type": "content_block_start", "index": 0, "content_block": block,
    }
    if block["type"] == "tool_use":
        delta = {"type": "input_json_delta", "partial_json": json.dumps(block["input"])}
    else:
        delta = {"type": "text_delta", "text": "LOCAL_TEST_DONE"}
    yield "content_block_delta", {"type": "content_block_delta", "index": 0, "delta": delta}
    yield "content_block_stop", {"type": "content_block_stop", "index": 0}
    yield "message_delta", {
        "type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None},
        "usage": {"output_tokens": 3},
    }
    yield "message_stop", {"type": "message_stop"}


def run_case(client, case, version):
    with tempfile.TemporaryDirectory(prefix="ccguard-real-client-") as raw_root:
        root = Path(raw_root)
        home, config, work = (root / name for name in ("home", "config", "work"))
        for path in (home, config, work):
            path.mkdir()
        install = config / "ccguard"
        (install / "lib").mkdir(parents=True)
        for name in ("pretool-gate.sh", "gate_check.py"):
            shutil.copy2(ROOT / "lib" / name, install / "lib" / name)
        (install / "state.env").write_text("CCGUARD_GATE=on\n", encoding="utf-8")

        hook = settings.hook_specs(install)["PreToolUse"]
        if case["kind"] == "startup_failure":
            hook["hooks"][0]["command"] = str(root / "missing-hook")
        elif case["kind"] == "timeout":
            hook["hooks"][0]["command"] = "python3 -c 'import time; time.sleep(3)'"
            hook["hooks"][0]["timeout"] = 1
        (config / "settings.json").write_text(
            json.dumps({"hooks": {"PreToolUse": [hook]}}), encoding="utf-8"
        )

        # A denied destructive command can only remove this disposable fixture.
        (work / ".ssh").mkdir()
        (work / ".ssh" / "sentinel").write_text("fake", encoding="utf-8")

        class Handler(BaseHTTPRequestHandler):
            requests = 0
            tool_result_is_error = None
            tool_result_mentions_hook = None

            def log_message(self, *_args):
                pass

            def do_POST(self):
                try:
                    size = int(self.headers.get("content-length", "0"))
                    body = json.loads(self.rfile.read(size))
                    assert self.path.startswith("/v1/messages")
                    assert any(tool.get("name") == "Bash" for tool in body.get("tools", []))
                    Handler.requests += 1
                    if Handler.requests > 1:
                        results = [part for message in body.get("messages", [])
                                   for part in message.get("content", [])
                                   if isinstance(part, dict) and part.get("type") == "tool_result"]
                        if results:
                            Handler.tool_result_is_error = results[-1].get("is_error", False)
                            Handler.tool_result_mentions_hook = "hook" in json.dumps(
                                results[-1], ensure_ascii=False
                            ).lower()
                    if Handler.requests == 1:
                        block = {
                            "type": "tool_use", "id": "toolu_local_test", "name": "Bash",
                            "input": {"command": case["command"], "description": "isolated test"},
                        }
                        reason = "tool_use"
                    else:
                        block = {"type": "text", "text": ""}
                        reason = "end_turn"
                    self.send_response(200)
                    self.send_header("content-type", "text/event-stream")
                    self.end_headers()
                    for event, obj in events(block, reason):
                        self.wfile.write(
                            ("event: " + event + "\ndata: " + json.dumps(obj) + "\n\n").encode()
                        )
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        # Deliberately do not inherit real API credentials or user configuration.
        env = {
            "HOME": str(home), "PATH": os.environ["PATH"], "TERM": "dumb",
            "CLAUDE_CONFIG_DIR": str(config),
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:%d" % server.server_port,
            "ANTHROPIC_API_KEY": "fake-local-test-key",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "DISABLE_UPDATES": "1",
            "CLAUDE_CODE_MAX_RETRIES": "0",
        }
        try:
            proc = subprocess.run(
                [client, "-p", "Run the supplied local test tool", "--model", "sonnet",
                 "--setting-sources", "user", "--tools", "Bash",
                 "--allowedTools", "Bash", "--output-format", "json"],
                cwd=work, env=env, text=True, capture_output=True, timeout=20,
                check=False,
            )
            try:
                response = json.loads(proc.stdout)
            except json.JSONDecodeError:
                response = {}
            actual = {
                "client_exit": proc.returncode,
                "api_requests": Handler.requests,
                "tool_result_is_error": Handler.tool_result_is_error,
                "tool_result_mentions_hook": Handler.tool_result_mentions_hook,
                "safe_marker_exists": (work / "safe-marker").exists(),
                "fake_ssh_exists": (work / ".ssh" / "sentinel").exists(),
                "client_completed": response.get("result") == "LOCAL_TEST_DONE",
            }
        except subprocess.TimeoutExpired:
            actual = {"client_timed_out": True}
        finally:
            server.shutdown()
            server.server_close()
        passed = all(actual.get(key) == expected for key, expected in case["expected"].items())
        return {
            "id": case["id"], "source": "real Claude Code CLI with local fake API",
            "input": case["command"], "initial_environment": "disposable HOME, config, workdir, fake API key, loopback relay",
            "expected_behavior": case["expected"], "actual_behavior": actual,
            "passed": passed, "client_version": version, "project_version": "0.2.0",
            "reason": case["reason"],
        }


CASES = [
    {"id": "RC001", "kind": "allow", "command": "printf SAFE > safe-marker",
     "expected": {"client_exit": 0, "api_requests": 2, "safe_marker_exists": True,
                  "fake_ssh_exists": True, "client_completed": True,
                  "tool_result_is_error": False, "tool_result_mentions_hook": False},
     "reason": "Normal local Bash command should pass the installed gate."},
    {"id": "RC002", "kind": "deny", "command": "rm -rf .ssh",
     "expected": {"client_exit": 0, "api_requests": 2, "safe_marker_exists": False,
                  "fake_ssh_exists": True, "client_completed": True,
                  "tool_result_is_error": True, "tool_result_mentions_hook": True},
     "reason": "The gate must stop a high-risk proposal before the disposable fixture is removed."},
    {"id": "RC003", "kind": "startup_failure", "command": "printf SAFE > safe-marker",
     "expected": {"client_exit": 0, "api_requests": 2, "safe_marker_exists": False,
                  "fake_ssh_exists": True, "client_completed": True,
                  "tool_result_is_error": True, "tool_result_mentions_hook": True},
     "reason": "onFailure=block must stop a command when the hook executable is missing."},
    {"id": "RC004", "kind": "timeout", "command": "printf SAFE > safe-marker",
     "expected": {"client_exit": 0, "api_requests": 2, "safe_marker_exists": False,
                  "fake_ssh_exists": True, "client_completed": True,
                  "tool_result_is_error": True, "tool_result_mentions_hook": True},
     "reason": "onFailure=block must stop a command when the hook exceeds its timeout."},
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", required=True, help="path to Claude Code v2.1.295+ binary")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    version = subprocess.check_output([args.client, "--version"], text=True).strip()
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", version)
    if not match or tuple(map(int, match.groups())) < (2, 1, 295):
        parser.error("Claude Code v2.1.295+ is required for onFailure=block")
    records = [run_case(args.client, case, version) for case in CASES]
    result = {"method": "real client, synthetic local API and tool proposals; no real model",
              "cases": records}
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0 if all(record["passed"] for record in records) else 1


if __name__ == "__main__":
    sys.exit(main())
