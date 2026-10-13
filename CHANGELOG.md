# Changelog

## 0.2.0 — 2026-10-13

- Removed the separate Bash keyword shortcut so all proposals reach the same checker.
- Made malformed input, unavailable checker, and checker crashes block locally; configured Claude Code v2.1.295+ to block hook launch failures and timeouts.
- Removed raw command text from gate logs and relay error bodies from probe output.
- Preserved co-located user hooks, quoted installation paths, protected shim targets, and prevented backup restore over later settings edits.
- Added isolated offline regression cases, original-versus-current records, a threat model, review findings, CI, and full Chinese/English documentation.

The release has no real-model injection efficacy measurement and no real Termux or Claude Code integration run.

## 0.1.0 — 2026-08-17

- Initial guarded, bare, raw, and probe launchers with prompt contract, Bash hook, installer, and tests (original commit `3007550`).
