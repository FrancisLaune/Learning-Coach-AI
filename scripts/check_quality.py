"""Run the local quality gate consistently on Windows, Linux and macOS."""

from __future__ import annotations

import subprocess
import sys

STEPS = (
    ("Ruff lint", [sys.executable, "-m", "ruff", "check", "."]),
    ("Ruff format", [sys.executable, "-m", "ruff", "format", "--check", "."]),
    ("MyPy", [sys.executable, "-m", "mypy"]),
    ("Pytest", [sys.executable, "-m", "pytest"]),
)


def main() -> int:
    for label, command in STEPS:
        print(f"\n==> {label}", flush=True)
        result = subprocess.run(command, check=False)
        if result.returncode:
            print(f"{label} failed with exit code {result.returncode}.", file=sys.stderr)
            return result.returncode
    print("\nAll quality checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
