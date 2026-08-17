# Security Policy

## Scope

This project adds prompt-level injection resistance and a local Claude Code
`PreToolUse` gate. Prompt text is not a cryptographic integrity mechanism: an
API relay can remove or rewrite it. The local gate is independent of the relay,
but it is intentionally a narrow pattern filter rather than a complete shell
sandbox.

## Reports

Open a GitHub security advisory for vulnerabilities that could expose local
secrets, bypass an advertised gate rule, corrupt Claude Code settings, or make
uninstall overwrite unrelated user configuration. Do not include real API
keys, private logs, or credential files in reports.

## Operational guidance

Review commands before granting permanent permission. Run `claude-probe` only
when an outbound test request is acceptable. `claude-bare` and `claude-raw`
disable this project's prompt anchor and local gate for that process.
