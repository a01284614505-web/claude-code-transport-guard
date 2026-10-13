"""Evaluate offline Bash proposals. This never executes a candidate command."""

import argparse
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "tests/cases.json").read_text())


def run_suite(label, source, cases):
    rows = []
    with tempfile.TemporaryDirectory(prefix="ccguard-cases-") as tmp:
        home = Path(tmp)
        (home / "lib").mkdir()
        (home / "logs").mkdir()
        shutil.copy(source / "gate_check.py", home / "lib/gate_check.py")
        (home / "state.env").write_text("CCGUARD_GATE=on\n")
        env = dict(os.environ, CCGUARD_HOME=tmp)
        for case in cases:
            payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": case["input"]}})
            start = time.perf_counter_ns()
            proc = subprocess.run(["bash", str(source / "pretool-gate.sh")], input=payload,
                                  text=True, capture_output=True, env=env, timeout=10)
            elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
            decision = "allow"
            if proc.returncode == 2:
                decision = "deny"
            elif proc.stdout.strip():
                try:
                    decision = json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]
                except (ValueError, KeyError, TypeError):
                    decision = "error"
            if proc.returncode not in (0, 2):
                decision = "error"
            rows.append({**case, "initial_environment": CASES["initial_environment"],
                         "version": label, "actual_behavior": decision,
                         "passed": decision == case["expected_behavior"],
                         "security_goal_met": (decision == "deny" if case["risk"] == "high" else decision == "allow"),
                         "elapsed_ms": round(elapsed_ms, 3)})
    return rows


def metrics(rows):
    high = [r for r in rows if r["risk"] == "high"]
    benign = [r for r in rows if r["risk"] == "benign"]
    return {"high_risk_cases": len(high), "false_negative_count": sum(r["actual_behavior"] != "deny" for r in high),
            "false_negative_rate": round(sum(r["actual_behavior"] != "deny" for r in high) / len(high), 4),
            "benign_cases": len(benign), "false_positive_count": sum(r["actual_behavior"] != "allow" for r in benign),
            "false_positive_rate": round(sum(r["actual_behavior"] != "allow" for r in benign) / len(benign), 4),
            "median_hook_ms": round(statistics.median(r["elapsed_ms"] for r in rows), 3)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compare-original", action="store_true")
    args = parser.parse_args()
    versions = {"v2-working-tree": ROOT / "lib"}
    with tempfile.TemporaryDirectory(prefix="ccguard-baseline-") as tmp:
        if args.compare_original:
            original = Path(tmp)
            for name in ("gate_check.py", "pretool-gate.sh"):
                content = subprocess.run(["git", "show", f"3007550:lib/{name}"], cwd=ROOT,
                                         check=True, capture_output=True).stdout
                (original / name).write_bytes(content)
            versions = {"original-3007550": original, **versions}
        results = {name: run_suite(name, path, CASES["cases"]) for name, path in versions.items()}
    report = {"schema": CASES["schema"], "environment": CASES["initial_environment"],
              "results": results, "metrics": {name: metrics(rows) for name, rows in results.items()},
              "model_behavior_tested": False}
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
    else:
        print(output)
    if any(not row["passed"] for row in results["v2-working-tree"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
