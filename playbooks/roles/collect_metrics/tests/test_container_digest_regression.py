#!/usr/bin/env python3
"""Test container digest collection with the real Podman module and fake CLI."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TEST = ROOT / "playbooks/roles/collect_metrics/tests/test.yml"
PREFIX = "registry.example.com/org/"
CASES = [
    ("multiple-distinct-digests", ["first:v1", "second:v2"], {"first:v1": "1111aaaa", "second:v2": "2222bbbb"}, None,
     "first_v1:1111aaaa;second_v2:2222bbbb;ci-lane:ci-lane-1"),
    ("first-module-failure", ["first:v1", "second:v2"], {"second:v2": "2222bbbb"}, "first:v1",
     "first_v1:N/A;second_v2:2222bbbb;ci-lane:ci-lane-1"),
    ("middle-module-failure", ["first:v1", "second:v2", "third:v3"], {"first:v1": "1111aaaa", "third:v3": "3333cccc"}, "second:v2",
     "first_v1:1111aaaa;second_v2:N/A;third_v3:3333cccc;ci-lane:ci-lane-1"),
]

FAKE_PODMAN = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["PODMAN_CALL_LOG"], "a") as log:
    log.write(json.dumps(args) + "\n")
if args[:2] == ["image", "exists"]:
    sys.exit(0)
if args[:2] != ["image", "inspect"]:
    sys.exit(2)
name = args[-1]
if name == os.environ.get("PODMAN_FAIL_IMAGE"):
    print("simulated podman image inspect failure", file=sys.stderr)
    sys.exit(1)
print(json.dumps([{"Digest": "sha256:" + json.loads(os.environ["PODMAN_DIGESTS"])[name]}]))
'''


def main():
    with tempfile.TemporaryDirectory(prefix="collect-metrics-digest-test-") as tmp:
        temp = Path(tmp)
        fake_bin = temp / "bin"
        fake_bin.mkdir()
        podman = fake_bin / "podman"
        podman.write_text(FAKE_PODMAN, encoding="utf-8")
        podman.chmod(0o755)
        for name, suffixes, digests, failure, expected in CASES:
            case = temp / name
            case.mkdir()
            images = [PREFIX + suffix for suffix in suffixes]
            out = case / "output" / "metrics.txt"
            calls = case / "podman-calls.jsonl"
            fixture = case / "fixture.yml"
            fixture.write_text(
                "collect_metrics_ci_lane: ci-lane-1\ncollect_metrics_list: []\n"
                f"collect_metrics_output_file: {json.dumps(str(out))}\ncollect_containers_list:\n"
                + "".join(f"  - {image}\n" for image in images)
                + f"expected_facts:\n  collect_metrics_attributes: {json.dumps(expected)}\n",
                encoding="utf-8",
            )
            ansible_tmp = case / "ansible-tmp"
            ansible_tmp.mkdir()
            env = os.environ.copy()
            env.update(
                PATH=f"{fake_bin}{os.pathsep}{env['PATH']}",
                PODMAN_CALL_LOG=str(calls),
                PODMAN_DIGESTS=json.dumps({PREFIX + key: value for key, value in digests.items()}),
                PODMAN_FAIL_IMAGE=PREFIX + failure if failure else "",
                ANSIBLE_STDOUT_CALLBACK="default",
                ANSIBLE_LOCAL_TEMP=str(ansible_tmp),
                ANSIBLE_REMOTE_TEMP=str(ansible_tmp),
            )
            result = subprocess.run(
                ["ansible-playbook", "-vv", str(TEST), "-e", f"@{fixture}"], cwd=ROOT,
                env=env, capture_output=True, text=True,
            )
            log = result.stdout + result.stderr
            if result.returncode:
                details = "\n".join(
                    line for line in log.splitlines()
                    if any(word in line.lower() for word in ("failed!", "fatal:", "expected", "undefined", "simulated", "object has no element"))
                )
                raise AssertionError(f"{name} failed:\n{details or log[-1000:]}")
            if not calls.exists():
                raise AssertionError(f"{name} made no fake Podman calls:\n{log}")
            podman_calls = [json.loads(line) for line in calls.read_text().splitlines()]
            for image in images:
                assert podman_calls.count(["image", "exists", image]) == 1, (name, image, podman_calls)
                assert podman_calls.count(["image", "inspect", image]) == 1, (name, image, podman_calls)
            if failure:
                failed_image = PREFIX + failure
                assert "simulated podman image inspect failure" in log, log[-3000:]
                assert "FAILED!" in log, log[-3000:]
                assert f"Failed to collect digest for {failed_image}, setting to N/A" in log
                assert "object has no element 0" not in log
            print(f"PASS {name}")
    print(f"PASS {len(CASES)} container digest regression cases")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        sys.exit(1)
