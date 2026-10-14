# Claude Code Transport Guard

[中文说明](README.md) · [Threat model](THREAT_MODEL.md) · [Research record](docs/research/REVIEW.md)

Version 0.2.0 adds a local, narrow `Bash` PreToolUse gate for Claude Code sessions using an untrusted API relay. It checks literal command text for selected dangerous patterns before execution. It does not proxy traffic, authenticate API messages, or sandbox a shell. The prompt contract and anchor are advisory; a relay can read or rewrite them.

Claude Code **v2.1.295 or later** is needed for the installed `onFailure: "block"` setting to block hook startup errors and timeouts. Offline rule cases ran on Linux. A real Claude Code v2.1.299 client was also tested against a local synthetic API for allow, deny, startup-failure, and timeout paths. No real model or Android Termux device was tested. Keep Claude Code's own permissions enabled.

## Install and modes

Requirements: Bash, Python 3, Claude Code. By default the tool installs under `$HOME/.local/bin` and `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/ccguard`, preserving your existing `claude` command.

```bash
./install.sh
ccguard status
claude-guarded
```

`claude-guarded` appends the defensive prompt and leaves the local Bash gate on. `claude-bare` replaces the system prompt with a minimal one and turns this project's prompt anchor and gate off. `claude-raw` uses an empty custom system prompt and also turns them off; tool use may become unreliable. Both unguarded modes still use Claude Code's own permissions. `claude-probe run` makes an explicit API request with a random marker; a clean echo does not prove relay integrity. It may store the returned text locally and was not run for this release.

To opt into a `claude` shim, run `./install.sh --with-claude-shim`. The installer refuses to replace a symlink owned by something else or a same-named unrelated launcher. `ccguard disable` and `ccguard enable` change the global state without deleting hooks. `ccguard uninstall` removes only this project's handlers and files. `ccguard uninstall --restore-backup` restores the pre-install settings and shim, but refuses to overwrite settings modified since install. Reinstall or uninstall may also stop if an installed launcher has changed; inspect and resolve that conflict manually.

## Scope, rules, and tests

The gate can catch selected remote-script pipes, reverse-shell syntax, credential exfiltration patterns, destructive deletion, disk writes, and attempts to overwrite guard files. It sees only the `Bash` tool's proposed command string. Variable expansion, encoded input, scripts, other interpreters, `Write`/`Edit`, and MCP tools remain outside its effective coverage. Rule definitions live in [lib/gate_check.py](lib/gate_check.py); change them with regression tests and reinstall to update the installed copy. There is no runtime rule override file.

```bash
bash tests/test-gate.sh
bash tests/test-install.sh
bash tests/test-termux-compat.sh
python3 tests/test-settings.py
python3 -m unittest discover -s tests -p 'test_v2_regression.py' -v
python3 tests/run_cases.py --compare-original --output docs/research/offline-results.json
python3 tests/run_agent_sim.py --output docs/research/agent-results.json
```

An optional real-client test uses a local fake API and requires Claude Code v2.1.295+:

```bash
python3 tests/test_real_client.py --client /path/to/claude --output docs/research/real-client-results.json
```

The original comparison requires commit `3007550` in local Git history. The static and fake-agent harnesses **never execute candidate commands** and do not call a model. On 19 selected static proposals, the original missed 6 of 14 high-risk samples; this version missed 4 of 14. Neither blocked the 5 benign samples. Four deterministic fake-agent cases exercise untrusted text flowing into candidate commands and the Hook. The real-client test executes only a harmless command in a disposable directory and targets a fake `.ssh` fixture for the denied command; its four lifecycle cases passed. These counts are not prompt-injection blocking rates or representative production estimates. Read the [method](docs/research/METHOD.md), [results](docs/research/RESULTS.md), and [confirmed self-audit findings](docs/research/FINDINGS.md) for the limits.

Report security issues privately as described in [SECURITY.md](SECURITY.md). Contributions and local validation are described in [CONTRIBUTING.md](CONTRIBUTING.md). Licensed under [MIT](LICENSE).
