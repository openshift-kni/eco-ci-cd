#!/usr/bin/env python3
"""Runs the ztp_deployment_timeline unit test matrix. See tests/README.md;
runner logic lives in tests/lib/ansible_role_test_runner.py (shared across
all role test suites)."""

import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(
    subprocess.run(
        ["git", "-C", str(SCRIPT_DIR), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
)
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))

from ansible_role_test_runner import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(SCRIPT_DIR))
