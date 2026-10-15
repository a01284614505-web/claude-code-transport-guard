# Changelog

## Unreleased — 2026-10-15

- Gate: inspect every `rm` operand instead of only the first, recognise split and long options (`-r -f`, `--recursive`) and quoted or braced `$HOME` (CCTG-008/009/010). A recursive flag is now sufficient for critical targets.
- Gate: catch remote scripts run through process substitution (`bash <(curl …)`) or wrappers such as `sudo -E` and `/usr/bin/env` (CCTG-011).
- Gate: stop treating words like `dataset`/`offset` as the `set` builtin (CCTG-012).
- Tests: `test_shim_requires_original_binary` now uses a minimal PATH so a real Claude Code on the test host cannot mask the result. Offline case G017 now expects `deny`.
- Added a reproducible, optional real-client Hook lifecycle test using Claude Code v2.1.299 and a local synthetic API. All four allow, deny, missing-Hook, and timeout cases passed on Linux; no real model or Android device was involved.

## 0.2.0 — 2026-10-13

- Removed the separate Bash keyword shortcut so all proposals reach the same checker.
- Made malformed input, unavailable checker, and checker crashes block locally; configured Claude Code v2.1.295+ to block hook launch failures and timeouts.
- Removed raw command text from gate logs and relay error bodies from probe output.
- Preserved co-located user hooks, quoted installation paths, protected shim targets, and prevented backup restore over later settings edits.
- Added preflight validation for settings and command-name collisions; prevented rollback from overwriting a later Claude launcher. Reinstall and uninstall refuse to remove a changed mode launcher.
- Added isolated offline regression cases, original-versus-current records, a threat model, review findings, CI, and full Chinese/English documentation.
- Added a deterministic fake-agent pipeline for untrusted text and a stub timeout check, clearly separate from real-model testing.

The release has no real-model injection efficacy measurement and no real Termux or Claude Code integration run.

## 0.1.0 — 2026-08-17

- Initial guarded, bare, raw, and probe launchers with prompt contract, Bash hook, installer, and tests (original commit `3007550`).
