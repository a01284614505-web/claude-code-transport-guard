# Security Policy

## Scope

This project adds prompt-level guidance and a local Claude Code
`PreToolUse` gate. Prompt text is not a cryptographic integrity mechanism: an
API relay can remove or rewrite it. The local gate is independent of the relay,
but it is intentionally a narrow pattern filter rather than a complete shell
sandbox.

Version 0.2.0 was validated offline on Linux only. Claude Code v2.1.295 or
later is required for `onFailure: "block"` to cover hook startup failures and
timeouts. Other tools, scripts, dynamic Shell expansion, and a compromised
local device remain outside this project's protection. See [THREAT_MODEL.md](THREAT_MODEL.md).

## Reports

Open a GitHub security advisory for vulnerabilities that could expose local
secrets, bypass an advertised gate rule, corrupt Claude Code settings, or make
uninstall overwrite unrelated user configuration. Do not include real API
keys, private logs, or credential files in reports.

Use a private advisory rather than a public issue for a newly discovered
security flaw. Include affected commit/version, prerequisites, a safe reproducer
using fake data, expected and actual behavior, impact, and any suggested fix.
Please allow maintainers time to reproduce and prepare a fix before public
disclosure. This project does not issue CVEs or claim third-party confirmation
without an actual external process.

## Operational guidance

Review commands before granting permanent permission. Run `claude-probe` only
when an outbound test request is acceptable. `claude-bare` and `claude-raw`
disable this project's prompt anchor and local gate for that process.
