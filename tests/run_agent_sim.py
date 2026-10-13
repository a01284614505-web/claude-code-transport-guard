"""Deterministic fake-agent integration, not a model prompt-injection test."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def proposed_command(untrusted_text):
    """Intentionally compliant fake agent: expose the local gate to a bad proposal."""
    return untrusted_text.split("PROPOSE_BASH: ", 1)[1].split("<", 1)[0].strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cases = json.loads((ROOT / "tests/agent_cases.json").read_text())["cases"]
    with tempfile.TemporaryDirectory(prefix="ccguard-agent-sim-") as tmp:
        home = Path(tmp)
        (home / "lib").mkdir()
        (home / "logs").mkdir()
        shutil.copy(ROOT / "lib/gate_check.py", home / "lib/gate_check.py")
        (home / "state.env").write_text("CCGUARD_GATE=on\n")
        env = dict(os.environ, CCGUARD_HOME=tmp)
        results = []
        for case in cases:
            proposal = proposed_command(case["input"])
            payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": proposal}})
            proc = subprocess.run(["bash", str(ROOT / "lib/pretool-gate.sh")], input=payload,
                                  capture_output=True, text=True, env=env, timeout=10)
            if proc.returncode == 2:
                actual = "deny"
            elif proc.stdout.strip():
                actual = json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]
            else:
                actual = "allow" if proc.returncode == 0 else "error"
            results.append({**case, "proposed_command": proposal, "version": "v2-working-tree",
                            "actual_behavior": actual, "passed": actual == case["expected_behavior"]})
    output = json.dumps({"schema": "ccguard-fake-agent-results-v1", "model_behavior_tested": False,
                         "candidate_commands_executed": False, "results": results}, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
    else:
        print(output)
    return 0 if all(row["passed"] for row in results) else 1


if __name__ == "__main__":
    sys.exit(main())
