#!/usr/bin/env python3
"""Runs the ocp_version_facts unit test matrix.

test.yml runs the role once and asserts the facts it produces against a
fixture's expected_facts / expected_undefined_facts (see README.md). This
runner invokes test.yml once per fixture in cases/, each as its own
`ansible-playbook` process.

That one-process-per-case split is deliberate, not incidental: the role
sets a lot of facts beyond its documented outputs (intermediate lookup
state, etc.), and Ansible has no reliable way to unset a fact once it's
been set. Looping over cases inside a single playbook run would let
set_fact state from one case bleed into the next - a case could pass not
because the role behaved correctly, but because a stale value from a
previous case happened to satisfy the assertion. A fresh process per case
gives every case a genuinely blank slate.
"""

import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CASES_DIR = SCRIPT_DIR / "cases"
TEST_PLAYBOOK = SCRIPT_DIR / "test.yml"

# Fixtures are trusted, hand-written YAML with a flat `expect_failure: true`
# key - a regex match avoids pulling in PyYAML just to read one boolean.
EXPECT_FAILURE_RE = re.compile(r"^expect_failure:\s*true\s*$", re.MULTILINE)


@dataclass
class CaseResult:
    name: str
    expect_failure: bool  # from the fixture's `expect_failure:` key
    actual_failure: bool  # whether ansible-playbook actually exited non-zero
    log_file: Path | None  # captured output; None once a passing case's log is discarded

    @property
    def passed(self) -> bool:
        """A case passes when the fixture's expectation matches reality,
        regardless of which way that goes: expected failures must fail,
        and everything else must succeed."""
        return self.actual_failure == self.expect_failure


def repo_root() -> Path:
    """Find the repo root so ansible-playbook can resolve ansible.cfg's
    (relative) roles_path regardless of where this script is invoked from."""
    result = subprocess.run(
        ["git", "-C", str(SCRIPT_DIR), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(result.stdout.strip())


def expects_failure(case_file: Path) -> bool:
    return bool(EXPECT_FAILURE_RE.search(case_file.read_text()))


def run_case(case_file: Path) -> CaseResult:
    """Run one fixture through test.yml in its own ansible-playbook process
    and capture its combined stdout/stderr to a temp file. The log is only
    useful for diagnosing a failure, so main() deletes it for passing cases
    and prints its path for failing ones."""
    name = case_file.stem
    expect_failure = expects_failure(case_file)

    fd, log_path = tempfile.mkstemp(prefix=f"{name}-")
    log_file = Path(log_path)
    with os.fdopen(fd, "w") as log:
        proc = subprocess.run(
            ["ansible-playbook", str(TEST_PLAYBOOK), "-e", f"@{case_file}"],
            stdout=log,
            stderr=subprocess.STDOUT,
        )

    result = CaseResult(name, expect_failure, proc.returncode != 0, log_file)
    if result.passed:
        log_file.unlink()
        result.log_file = None

    return result


def main() -> int:
    os.chdir(repo_root())

    # The repo's ansible.cfg sets stdout_callback=yaml (community.general),
    # which crashes under some newer Python/PyYAML combinations. Override it
    # for the test runner only - it doesn't affect the assertions, and the
    # plain output reads fine for pass/fail purposes.
    os.environ["ANSIBLE_STDOUT_CALLBACK"] = "default"

    # Print each result as its case finishes rather than batching output
    # until the end - a full run is several seconds per case, and a runner
    # that goes silent for a while looks hung.
    results = []
    for case_file in sorted(CASES_DIR.glob("*.yml")):
        result = run_case(case_file)
        results.append(result)

        if result.passed:
            print(f"PASS  {result.name}", flush=True)
        else:
            got = "fail" if result.actual_failure else "pass"
            print(
                f"FAIL  {result.name}  (expected_failure={str(result.expect_failure).lower()}, "
                f"got={got}, log: {result.log_file})",
                flush=True,
            )

    failed = [result for result in results if not result.passed]
    print("----")
    print(f"{len(results) - len(failed)} passed, {len(failed)} failed")

    if failed:
        print("Failed:", " ".join(result.name for result in failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
