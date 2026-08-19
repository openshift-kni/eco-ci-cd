#!/usr/bin/env python3
"""Runs the container_image_mirror live integration tests. See README.md.

Unlike ../mock/run_tests.py (mocked unit tests, one fresh ansible-playbook
process per fixture via tests/lib/ansible_role_test_runner.py), these cases
exercise the role's real skopeo copy, registry tag-list check, and (for
remove) real file deletion - against a single ephemeral registry instance
started once for the whole run and shared across cases. That different
lifecycle (setup/teardown around a long-lived process, not just spawning
ansible-playbook) is why this is a standalone script rather than another
caller of the shared per-case runner.
"""

import crypt
import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
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

from ansible_role_test_runner import expects_failure  # noqa: E402

# Fixtures that need the authenticated registry (see LocalRegistry's `auth`
# param) set a flat `_use_auth_registry: true` key - same convention as
# `expect_failure: true`, sniffed with a regex rather than a YAML parse for
# the same reason ansible_role_test_runner does it that way.
USE_AUTH_REGISTRY_RE = re.compile(r"^_use_auth_registry:\s*true\s*$", re.MULTILINE)

# Fixtures that rely on a real permission-denied failure (e.g. real removal
# failures) only get one under a non-root UID - root bypasses Linux's DAC
# permission checks entirely, so the same scenario silently succeeds
# instead of failing when this runner itself is invoked as root. Skipped
# with a clear reason rather than run (would spuriously fail
# `expect_failure: true` under root) or silently dropped.
REQUIRES_NON_ROOT_RE = re.compile(r"^_requires_non_root:\s*true\s*$", re.MULTILINE)
IS_ROOT = os.geteuid() == 0

REGISTRY_VERSION = "3.1.1"
RELEASE_BASE = f"https://github.com/distribution/distribution/releases/download/v{REGISTRY_VERSION}"
CACHE_DIR = Path(tempfile.gettempdir()) / "container-image-mirror-it" / f"registry-{REGISTRY_VERSION}"

# Pinned at review time from the same release's published .sha256 files,
# rather than fetched from GitHub at run time - fetching the hash from the
# same release it's meant to verify only catches transit corruption, not a
# compromised upstream artifact. Bumping REGISTRY_VERSION requires adding a
# new entry here deliberately.
EXPECTED_SHA256 = {
    "amd64": "6f330a3ba9ea1d23a6ee189f449d792595240585bb2f159123d76ac594f70dd8",
    "arm64": "8167316d2b4a57e10d44f8c8a3c75fea5f3ec1c71872760bb903e5e8e52e9ad6",
}

GOARCH_BY_MACHINE = {
    "x86_64": "amd64",
    "amd64": "amd64",
    "aarch64": "arm64",
    "arm64": "arm64",
}


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def ensure_registry_binary():
    """Download and cache the pinned distribution/distribution 'registry'
    static binary under /tmp, verifying its published sha256. This needs no
    container engine and no root - /tmp is world-writable even under
    OpenShift's arbitrary-UID SCC (the same class of constraint fixed for
    Ansible's own tmp dir in PR #641)."""
    binary = CACHE_DIR / "registry"
    if binary.is_file() and os.access(binary, os.X_OK):
        return binary

    machine = platform.machine()
    arch = GOARCH_BY_MACHINE.get(machine)
    if not arch:
        fail(f"unsupported architecture for the registry binary: {machine}")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    asset = f"registry_{REGISTRY_VERSION}_linux_{arch}.tar.gz"
    tarball = CACHE_DIR / asset

    print(f"Fetching {asset}...")
    urllib.request.urlretrieve(f"{RELEASE_BASE}/{asset}", tarball)
    expected_sha256 = EXPECTED_SHA256[arch]
    actual_sha256 = hashlib.sha256(tarball.read_bytes()).hexdigest()
    if actual_sha256 != expected_sha256:
        tarball.unlink()
        fail(f"{asset} checksum mismatch: expected {expected_sha256}, got {actual_sha256}")

    # Read the member's bytes out and write them ourselves rather than
    # tar.extract() - Python 3.9 predates the extraction `filter=` safety
    # check (added in 3.12), so .extract() would follow a member crafted as
    # a symlink. Reading bytes out of the (now checksum-verified) tarball
    # and writing a plain file can't create a symlink or special file.
    with tarfile.open(tarball) as tar:
        member = tar.getmember("registry")
        if not member.isfile():
            fail(f"{asset}'s 'registry' member is not a regular file")
        binary.write_bytes(tar.extractfile(member).read())
    tarball.unlink()
    binary.chmod(0o755)
    return binary


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class LocalRegistry:
    """An ephemeral registry instance, played as this suite's mirror
    *destination* only. The mirror source is the real
    registry.access.redhat.com, reached over the network like production
    traffic - we don't stand that up.

    With `auth=None` (the default), this is the single shared instance
    covering both the mirror case (copies into it) and the remove case
    (test.yml seeds an image into it for real, then the role under test
    deletes it from it). Pass `auth=(username, password)` for a second,
    separate instance that requires HTTP basic auth on every request - the
    only way to test the role's real pull-secret path, and it has to be a
    distinct instance since enabling auth would break the anonymous cases
    sharing the same server."""

    def __init__(self, binary, auth=None):
        self.binary = binary
        self.auth = auth
        self.scratch_dir = Path(tempfile.mkdtemp(prefix="container-image-mirror-it-"))
        self.data_path = self.scratch_dir / "data" / "docker" / "registry" / "v2" / "repositories"
        self.port = free_port()
        self.process = None
        self.log_file = None

    def start(self):
        config_text = (
            "version: 0.1\n"
            "log:\n"
            "  level: warn\n"
            "storage:\n"
            "  filesystem:\n"
            f"    rootdirectory: {self.scratch_dir / 'data'}\n"
            "http:\n"
            f"  addr: 127.0.0.1:{self.port}\n"
        )
        if self.auth:
            username, password = self.auth
            # crypt.METHOD_BLOWFISH is bcrypt - the only hash format the
            # registry's htpasswd backend accepts. Available in the stdlib
            # `crypt` module on glibc systems (this image's UBI9 base), so
            # no extra package (e.g. httpd-tools) is needed just for this.
            bcrypt_hash = crypt.crypt(password, crypt.mksalt(crypt.METHOD_BLOWFISH))
            htpasswd_path = self.scratch_dir / "htpasswd"
            htpasswd_path.write_text(f"{username}:{bcrypt_hash}\n")
            config_text += (
                "auth:\n"
                "  htpasswd:\n"
                '    realm: "container_image_mirror integration tests"\n'
                f"    path: {htpasswd_path}\n"
            )
        config_path = self.scratch_dir / "config.yml"
        config_path.write_text(config_text)
        self.log_file = open(self.scratch_dir / "registry.log", "w")
        self.process = subprocess.Popen(
            [str(self.binary), "serve", str(config_path)],
            stdout=self.log_file,
            stderr=subprocess.STDOUT,
        )
        self._wait_ready()

    def _wait_ready(self, timeout=10.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                fail(f"registry process exited early - see {self.log_file.name}")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/v2/", timeout=1) as resp:
                    if resp.status == 200:
                        return
            except urllib.error.HTTPError as e:
                # The auth-enabled instance correctly answers /v2/ with 401
                # (no credentials sent) - that still proves it's up.
                if e.code == 401:
                    return
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(0.25)
        fail(f"registry did not become ready within {timeout}s - see {self.log_file.name}")

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        if self.log_file:
            self.log_file.close()
        # A case testing a real permission failure (see
        # REQUIRES_NON_ROOT_RE) may leave a directory chmod'd read-only -
        # restore write access everywhere before rmtree, or cleanup itself
        # would silently leave that directory behind.
        for root, dirs, _files in os.walk(self.scratch_dir):
            os.chmod(root, 0o755)
        shutil.rmtree(self.scratch_dir, ignore_errors=True)


def run_case(test_playbook, case_file, anon_registry, auth_registry):
    name = case_file.stem
    expect_failure = expects_failure(case_file)
    use_auth = bool(USE_AUTH_REGISTRY_RE.search(case_file.read_text()))
    registry = auth_registry if use_auth else anon_registry

    runtime_vars = {
        "container_image_mirror_registry_port": registry.port,
        "container_image_mirror_registry_data_path": str(registry.data_path),
    }
    if use_auth:
        username, password = auth_registry.auth
        runtime_vars["_registry_auth_username"] = username
        runtime_vars["_registry_auth_password"] = password

    # Passed as a JSON extra-vars file rather than `-e key=value` on argv -
    # the auth case's password would otherwise sit in plain sight of any
    # co-resident process via `ps`/`/proc/<pid>/cmdline` for the process's
    # lifetime. Low real risk (a random, single-run credential gating a
    # throwaway loopback registry torn down at the end of this same run),
    # but avoiding it costs nothing.
    fd, vars_path = tempfile.mkstemp(prefix=f"{name}-vars-", suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(runtime_vars, f)

    fd, log_path = tempfile.mkstemp(prefix=f"{name}-")
    log_file = Path(log_path)
    try:
        with os.fdopen(fd, "w") as log:
            proc = subprocess.run(
                [
                    "ansible-playbook", str(test_playbook),
                    "-e", f"@{case_file}",
                    "-e", f"@{vars_path}",
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
            )
    finally:
        os.unlink(vars_path)

    actual_failure = proc.returncode != 0
    passed = actual_failure == expect_failure
    if passed:
        log_file.unlink()
        log_file = None
    return name, passed, expect_failure, actual_failure, log_file


def main():
    if shutil.which("skopeo") is None:
        fail(
            "skopeo not found on PATH - see "
            "playbooks/roles/container_image_mirror/tests/integration/README.md. "
            "The eco-ci-cd image installs it via the Containerfile; "
            "install it locally to run this suite outside a container."
        )

    os.chdir(REPO_ROOT)
    os.environ["ANSIBLE_STDOUT_CALLBACK"] = "default"
    tmp_dir = tempfile.mkdtemp(prefix="ansible-role-test-tmp-")
    os.environ["ANSIBLE_LOCAL_TEMP"] = tmp_dir
    os.environ["ANSIBLE_REMOTE_TEMP"] = tmp_dir

    binary = ensure_registry_binary()
    anon_registry = LocalRegistry(binary)
    auth_registry = LocalRegistry(binary, auth=(secrets.token_hex(8), secrets.token_hex(16)))
    results = []
    skipped = []
    try:
        anon_registry.start()
        auth_registry.start()

        test_playbook = SCRIPT_DIR / "test.yml"
        cases_dir = SCRIPT_DIR / "cases"
        for case_file in sorted(cases_dir.glob("*.yml")):
            if IS_ROOT and REQUIRES_NON_ROOT_RE.search(case_file.read_text()):
                print(f"SKIP  {case_file.stem}  (requires a non-root UID - running as root)")
                skipped.append(case_file.stem)
                continue

            name, passed, expect_failure, actual_failure, log_file = run_case(
                test_playbook, case_file, anon_registry, auth_registry
            )
            results.append((name, passed))
            if passed:
                print(f"PASS  {name}")
            else:
                got = "fail" if actual_failure else "pass"
                print(
                    f"FAIL  {name}  (expected_failure={str(expect_failure).lower()}, "
                    f"got={got}, log: {log_file})"
                )
    finally:
        anon_registry.stop()
        auth_registry.stop()

    failed = [name for name, passed in results if not passed]
    print("----")
    print(f"{len(results) - len(failed)} passed, {len(failed)} failed, {len(skipped)} skipped")
    if failed:
        print("Failed:", " ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
