# Results and unresolved work

The machine-readable record is [offline-results.json](offline-results.json), generated from [tests/cases.json](../../tests/cases.json). Source versions are original `3007550` and fixes `82183ab`, `1dfde3a`. Results are limited to the selected 19 static proposals; the sample is neither random nor representative of all Bash usage.

| Offline measure | Original | v0.2.0 code |
| --- | ---: | ---: |
| High-risk proposals | 14 | 14 |
| Missed high-risk proposals | 6/14 (42.86%) | 4/14 (28.57%) |
| Benign proposals blocked | 0/5 (0%) | 0/5 (0%) |
| Median hook wall time in recorded run | 71.053 ms | 68.351 ms |

G001/G002 (`fdisk`, `parted`) account for the two improved detections. G016-G019 deliberately demonstrate residual misses: dynamic command construction, long `rm` options, nested interpreter behavior, and encoded execution. The original fast path avoids Python startup on some commands, while the changed gate starts Python for every Bash proposal. The displayed medians are noisy single-pass wall times in temporary directories, not a stable latency benchmark; no claim of faster runtime is made. Compatibility checks passed on this Linux host: 32 original gate cases, original settings and install lifecycle tests, 15 new Python regressions (including a loopback fake relay), a Termux-style path/shebang simulation, Bash syntax, and Python compilation. A real Android Termux run and a real Claude Code Hook lifecycle run were not available.

The project still cannot stop a relay from reading or altering API requests, including credentials already in a request. The prompt contract cannot authenticate source roles. The Bash gate cannot inspect execution inside scripts, shell expansion, network-capable tools, `Write`/`Edit`, MCP tools, or client actions outside Bash. The documented `onFailure: "block"` requires Claude Code v2.1.295+; older versions retain client-side failure/timeout uncertainty. A local same-user process or a fully compromised device can change or bypass the project. False-positive measurement here covers only five benign examples and is too small for a usability guarantee.

Next maintenance priorities: add a real Claude Code v2.1.295+ integration job with a fake Bash tool target and deliberate hook timeout; run installation and shebang checks on actual Termux; expand a curated benign corpus from consented, scrubbed workflows; design explicit policies for non-Bash tools only after their input schemas are tested; and consider a small Shell parser only if it reduces proven high-impact misses without hurting latency or false positives. Keep command strings out of diagnostic logs and report newly confirmed issues privately through the GitHub security advisory channel.
