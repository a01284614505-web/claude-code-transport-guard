# Contributing

Keep the gate small and its claims narrow. Add a fake, offline failing regression case before changing an important rule. Never run a proposed attack command in tests; pass its text as JSON to the Hook. Use reserved example domains and fake credentials. Avoid broad regex additions that are hard to explain or likely to block normal development. Prefer a documented uncovered case when static inspection cannot decide safely.

Before submitting a change, run the commands in [README.md](README.md) and `bash -n install.sh bin/* lib/*.sh tests/*.sh`. Include the tested OS, Bash/Python versions, and whether Claude Code and Termux were actually used. If a rule changes, update `tests/cases.json`, regenerate the comparison only when the original commit is available, and explain any false-positive or latency tradeoff. Do not change a failing expectation merely to make CI green.

For a suspected vulnerability, follow [SECURITY.md](SECURITY.md) and use fake data. Do not post credentials, private logs, real relay traffic, or exploit attempts against third-party systems.
