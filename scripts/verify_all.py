"""
Unified Verification Script for SIMS 4 Mods Manager.
Executes linting (Ruff), type checking (Mypy), and automated test suites (Pytest).
"""

import subprocess
import sys
import time
from typing import List, Tuple


def run_step(name: str, cmd: List[str]) -> Tuple[bool, float, str]:
    print(f"\n[+] Running {name}: {' '.join(cmd)}")
    start = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - start
    output = (res.stdout + "\n" + res.stderr).strip()
    return res.returncode == 0, elapsed, output


def main() -> int:
    print("=" * 60)
    print("SIMS 4 MODS MANAGER - FULL QUALITY & RESILIENCE AUDIT")
    print("=" * 60)

    steps = [
        ("Linting & Code Style (Ruff)", ["uv", "run", "ruff", "check", "."]),
        ("Strict Type Checking (Mypy)", ["uv", "run", "mypy", "src/"]),
        ("Documentation Build (MkDocs strict)", ["uv", "run", "mkdocs", "build", "--strict"]),
        ("Test Suites & Coverage (Pytest)", ["uv", "run", "pytest", "-q", "--cov=src", "--cov-report=term-missing:skip-covered"]),
    ]

    all_ok = True
    summaries = []

    for name, cmd in steps:
        ok, elapsed, out = run_step(name, cmd)
        status = "PASSED" if ok else "FAILED"
        summaries.append((name, status, elapsed))
        if not ok:
            all_ok = False
            print(f"[!] {name} failed:\n{out}")
        else:
            print(f"[*] {name} passed in {elapsed:.2f}s")

    print("\n" + "=" * 60)
    print("AUDIT SUMMARY:")
    print("=" * 60)
    for name, status, elapsed in summaries:
        print(f" - {name:<35} : [{status}] in {elapsed:.2f}s")

    if all_ok:
        print("\nAll quality gates passed successfully! System is GREEN.")
        return 0
    else:
        print("\nQuality gate failure detected. Please fix the reported issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
