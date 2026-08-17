#!/usr/bin/env python3
"""Install, inspect, and remove ccguard-owned Claude Code hooks."""

import argparse
import json
import os
from pathlib import Path

MARKER = "ccguard-managed"


def hook_specs(install_dir):
    return {
        "PreToolUse": {
            "matcher": "Bash",
            "hooks": [{
                "type": "command",
                "command": str(install_dir / "lib" / "pretool-gate.sh"),
                "timeout": 10,
                "statusMessage": MARKER,
            }],
        },
        "UserPromptSubmit": {
            "hooks": [{
                "type": "command",
                "command": str(install_dir / "lib" / "prompt-anchor.sh"),
                "timeout": 5,
                "statusMessage": MARKER,
            }],
        },
    }


def is_owned(entry):
    for hook in entry.get("hooks", []):
        command = hook.get("command", "")
        if hook.get("statusMessage") == MARKER or "/ccguard/lib/" in command:
            return True
    return False


def load(path):
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("settings root must be a JSON object")
    return data


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".ccguard.tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.chmod(temp, 0o600)
    temp.replace(path)


def install(data, install_dir):
    hooks = data.setdefault("hooks", {})
    specs = hook_specs(install_dir)
    for event, spec in specs.items():
        entries = hooks.setdefault(event, [])
        entries[:] = [entry for entry in entries if not is_owned(entry)]
        entries.append(spec)
    return data


def remove(data):
    hooks = data.get("hooks", {})
    for event in list(hooks):
        entries = [entry for entry in hooks[event] if not is_owned(entry)]
        if entries:
            hooks[event] = entries
        else:
            del hooks[event]
    if not hooks:
        data.pop("hooks", None)
    return data


def status(data):
    hooks = data.get("hooks", {})
    return {
        event: sum(1 for entry in hooks.get(event, []) if is_owned(entry))
        for event in ("PreToolUse", "UserPromptSubmit")
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("install", "remove", "status"))
    parser.add_argument("settings", type=Path)
    parser.add_argument("install_dir", nargs="?", type=Path)
    args = parser.parse_args()
    data = load(args.settings)
    if args.action == "install":
        if args.install_dir is None:
            parser.error("install_dir is required for install")
        save(args.settings, install(data, args.install_dir.resolve()))
    elif args.action == "remove":
        save(args.settings, remove(data))
    else:
        print(json.dumps(status(data), sort_keys=True))


if __name__ == "__main__":
    main()
