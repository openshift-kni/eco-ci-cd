"""Shared runner for per-role Ansible unit test suites.

Each role's tests/test.yml runs the role once and asserts the facts it
produces against a fixture's expected_facts / expected_undefined_facts (see
that role's tests/README.md). This runner invokes test.yml once per fixture
in cases/, each as its own `ansible-playbook` process.

That one-process-per-case split is deliberate, not incidental: roles set a
lot of facts beyond their documented outputs (intermediate lookup state,
etc.), and Ansible has no reliable way to unset a fact once it's been set.
Looping over cases inside a single playbook run would let set_fact state
from one case bleed into the next - a case could pass not because the role
behaved correctly, but because a stale value from a previous case happened
to satisfy the assertion. A fresh process per case gives every case a
genuinely blank slate.

This module holds the runner logic shared by every role's tests/run_tests.py
wrapper. It is intentionally role-agnostic: it knows nothing about any
specific role's input vars, only the cases/*.yml + test.yml conventions
documented in each role's tests/README.md.
"""

import difflib
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Fixtures are trusted, hand-written YAML with a flat `expect_failure: true`
# key - a regex match avoids pulling in PyYAML just to read one boolean.
EXPECT_FAILURE_RE = re.compile(r"^expect_failure:\s*true\s*$", re.MULTILINE)

# ansible.cfg forces color output, so captured logs are full of ANSI escapes.
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")

# test.yml's assert tasks always phrase a failure as "<fact>: expected 'X',
# got 'Y'" or "<fact> was expected to be unset but got 'Y'" - both contain
# "expected" followed later by "got", which their success_msg counterparts
# never do. Matching that shape pulls the actual-vs-expected value straight
# out of the captured ansible-playbook output.
ASSERT_DIFF_RE = re.compile(r'"msg":\s*"([^"]*?expected[^"]*?got[^"]*?)"')

# Pulls the quoted expected/got values out of a diff line, e.g.
# "ocp_version_facts_major: expected '5', got '4'", so only the parts of
# *those values* that actually differ can be colored - not the whole value.
DIFF_PAIR_RE = re.compile(r"^(.*expected ')([^']*)(', got ')([^']*)('.*)$")
# Fallback for the "X was expected to be unset but got 'Y'" phrasing, which
# has no quoted expected value to diff against.
DIFF_GOT_ONLY_RE = re.compile(r"^(.*got ')([^']*)('.*)$")

_GREEN = "\x1b[32m"
_RED = "\x1b[31m"
_BOLD = "\x1b[1m"
_RESET = "\x1b[0m"
# Respect NO_COLOR (https://no-color.org) and disable automatically when
# output isn't a terminal (piped to a file/CI log), same as tools like git.
# CLICOLOR_FORCE (BSD/ripgrep/bat convention) overrides the isatty check for
# non-tty contexts that still render ANSI, e.g. CI log viewers.
_COLOR = "NO_COLOR" not in os.environ and (
    sys.stdout.isatty() or os.environ.get("CLICOLOR_FORCE") == "1"
)


def _color(text: str, *codes: str) -> str:
    if not _COLOR:
        return text
    return "".join(codes) + text + _RESET


def _char_diff(expected: str, got: str) -> tuple[str, str]:
    """Color only the segments where expected/got actually differ, leaving
    everything they have in common in the default color - a long shared
    prefix/suffix around a one-character difference shouldn't all light up."""
    matcher = difflib.SequenceMatcher(a=expected, b=got, autojunk=False)
    exp_out, got_out = [], []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        exp_seg, got_seg = expected[i1:i2], got[j1:j2]
        if tag == "equal":
            exp_out.append(exp_seg)
            got_out.append(got_seg)
        else:
            if exp_seg:
                exp_out.append(_color(exp_seg, _GREEN, _BOLD))
            if got_seg:
                got_out.append(_color(got_seg, _RED, _BOLD))
    return "".join(exp_out), "".join(got_out)


def highlight_diff(diff: str) -> str:
    """Color just the differing part of the expected/got values in an
    assertion diff line - e.g. only the '1' vs '0' in
    "worker-1_kernel..." vs "worker-0_kernel..." gets colored, not the
    whole value."""
    pair_match = DIFF_PAIR_RE.match(diff)
    if pair_match:
        before, expected, middle, got, after = pair_match.groups()
        exp_highlighted, got_highlighted = _char_diff(expected, got)
        return f"{before}{exp_highlighted}{middle}{got_highlighted}{after}"

    # "X was expected to be unset but got 'Y'" - no expected value to diff
    # against, so just mark the unexpected value red in its entirety.
    got_only_match = DIFF_GOT_ONLY_RE.match(diff)
    if got_only_match:
        before, got, after = got_only_match.groups()
        return f"{before}{_color(got, _RED, _BOLD)}{after}"

    return diff


@dataclass
class CaseResult:
    name: str
    expect_failure: bool  # from the fixture's `expect_failure:` key
    actual_failure: bool  # whether ansible-playbook actually exited non-zero
    log_file: Optional[Path]  # captured output; None once a passing case's log is discarded

    @property
    def passed(self) -> bool:
        """A case passes when the fixture's expectation matches reality,
        regardless of which way that goes: expected failures must fail,
        and everything else must succeed."""
        return self.actual_failure == self.expect_failure


def repo_root(script_dir: Path) -> Path:
    """Find the repo root so ansible-playbook can resolve ansible.cfg's
    (relative) roles_path regardless of where this script is invoked from."""
    result = subprocess.run(
        ["git", "-C", str(script_dir), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(result.stdout.strip())


def expects_failure(case_file: Path) -> bool:
    return bool(EXPECT_FAILURE_RE.search(case_file.read_text()))


def assertion_diffs(log_file: Path) -> list[str]:
    """Pull the actual-vs-expected value out of a failed case's captured
    output, e.g. "ocp_version_facts_major: expected '5', got '4'"."""
    text = ANSI_ESCAPE_RE.sub("", log_file.read_text())
    seen = []
    for match in ASSERT_DIFF_RE.finditer(text):
        if match.group(1) not in seen:
            seen.append(match.group(1))
    return seen


def run_case(test_playbook: Path, case_file: Path) -> CaseResult:
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
            ["ansible-playbook", str(test_playbook), "-e", f"@{case_file}"],
            stdout=log,
            stderr=subprocess.STDOUT,
        )

    result = CaseResult(name, expect_failure, proc.returncode != 0, log_file)
    if result.passed:
        log_file.unlink()
        result.log_file = None

    return result


def main(script_dir: Path) -> int:
    """Run every cases/*.yml fixture under script_dir through script_dir's
    test.yml. Intended to be called from a role's tests/run_tests.py with
    script_dir = that file's own directory."""
    cases_dir = script_dir / "cases"
    test_playbook = script_dir / "test.yml"

    os.chdir(repo_root(script_dir))

    # The repo's ansible.cfg sets stdout_callback=yaml (community.general),
    # which crashes under some newer Python/PyYAML combinations. Override it
    # for the test runner only - it doesn't affect the assertions, and the
    # plain output reads fine for pass/fail purposes.
    os.environ["ANSIBLE_STDOUT_CALLBACK"] = "default"

    # Print each result as its case finishes rather than batching output
    # until the end - a full run is several seconds per case, and a runner
    # that goes silent for a while looks hung.
    results = []
    for case_file in sorted(cases_dir.glob("*.yml")):
        result = run_case(test_playbook, case_file)
        results.append(result)

        if result.passed:
            print(f"{_color('PASS', _GREEN, _BOLD)}  {result.name}", flush=True)
        else:
            got = "fail" if result.actual_failure else "pass"
            print(
                f"{_color('FAIL', _RED, _BOLD)}  {result.name}  "
                f"(expected_failure={str(result.expect_failure).lower()}, "
                f"got={got}, log: {result.log_file})",
                flush=True,
            )
            for diff in assertion_diffs(result.log_file):
                print(f"        {highlight_diff(diff)}", flush=True)

    failed = [result for result in results if not result.passed]
    print("----")
    passed_count = _color(str(len(results) - len(failed)), _GREEN)
    failed_count = _color(str(len(failed)), _RED) if failed else "0"
    print(f"{passed_count} passed, {failed_count} failed")

    if failed:
        print(_color("Failed:", _RED), " ".join(result.name for result in failed))
        return 1
    return 0
