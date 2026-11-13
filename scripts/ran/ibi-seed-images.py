#!/usr/bin/env python3
"""Plan, copy and verify the images required by an IBI seed.

Usage: ibi-seed-images.py MODE DIRECTORY KUBECONFIG BUDGET_SECONDS
Modes: prepare, plan, transfer, verify. The caller creates a private working
folder containing config.json and the inputs required by the selected mode.
Only the report/ subdirectory is safe to collect as a CI artifact.
"""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

DIGEST = re.compile(r"sha256:[a-f0-9]{64}")
REFERENCE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9./_:@-]*")


class MirrorError(Exception):
    """An intentionally sanitized operation or validation failure."""


class SeedImages:
    """One invocation with an isolated working directory and execution budget."""

    def __init__(self, directory, kubeconfig, budget):
        self.work = Path(directory)
        self.kubeconfig = kubeconfig
        self.config = json.loads((self.work / "config.json").read_text())
        self.registry = self.config["registry"]
        self.endpoint = self.config["endpoint"]
        self.started = time.monotonic()
        self.deadline = self.started + int(budget)
        (self.work / "report").mkdir(exist_ok=True)

    def run(self, args, operation, timeout=600):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise MirrorError("Mirror execution budget exhausted before " + operation)
        try:
            result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    timeout=min(timeout, remaining), check=False, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            raise MirrorError(operation + " timed out") from None
        if result.returncode:
            # Registry/oc stderr can include credentials or cluster URLs.
            raise MirrorError(operation + " failed (exit " + str(result.returncode) + ")")
        return result.stdout

    def write(self, name, value):
        path = self.work / name
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, indent=2) + "\n")
        temporary.replace(path)
        if name in {"plan.json", "copy-results.json", "verify-results.json", "verified.json", "failure.json"}:
            (self.work / "report" / name).write_text(path.read_text())

    def oc(self, *args):
        return json.loads(self.run(["oc", "--kubeconfig", self.kubeconfig, "--request-timeout=60s",
                               *args, "-o", "json"], "Read hub configuration", 90))

    def sha(self, raw):
        return "sha256:" + hashlib.sha256(raw).hexdigest()

    def split(self, ref):
        if not REFERENCE.fullmatch(ref) or "/" not in ref or ".." in ref:
            raise MirrorError("Invalid image reference")
        if "@" in ref:
            repo, value = ref.rsplit("@", 1)
            if not DIGEST.fullmatch(value):
                raise MirrorError("Only sha256 image digests are supported")
            return repo, value, True
        if ":" not in ref.rsplit("/", 1)[-1]:
            ref += ":latest"
        repo, value = ref.rsplit(":", 1)
        if not value:
            raise MirrorError("Empty image tag")
        return repo, value, False

    def raw(self, ref, auth="auth.json"):
        self.split(ref)
        return self.run(["skopeo", "inspect", "--raw", "--tls-verify=false",
                    "--authfile", str(self.work / auth), "docker://" + ref], "Read manifest " + ref, 90)

    def check(self, ref, digest, auth="auth.json"):
        if self.sha(self.raw(ref, auth)) != digest:
            raise MirrorError("Manifest digest mismatch: " + ref)

    def copy(self, source, destination, destination_auth):
        self.run(["skopeo", "copy", "--all", "--preserve-digests", "--retry-times", "2",
             "--src-authfile", str(self.work / "auth.json"),
             "--dest-authfile", str(self.work / destination_auth),
             "--src-tls-verify=false", "--dest-tls-verify=false",
             "docker://" + source, "docker://" + destination], "Copy image " + source, 1800)

    def dynamic_mirror(self, source, idms):
        mirrors = {mirror for item in idms["items"]
                   for entry in item.get("spec", {}).get("imageDigestMirrors", [])
                   if entry["source"] == source
                   for mirror in entry.get("mirrors", []) if mirror.startswith(self.registry + "/")}
        if len(mirrors) != 1:
            raise MirrorError("Expected one local ACM/MCE mirror for " + source)
        return mirrors.pop()

    def mappings(self, template, idms):
        # Parse only imageDigestSources; the rest of this document is a Go template.
        blocks = re.findall(r"^imageDigestSources:\s*\n((?:[ \t].*\n|[ \t]*\n)*)",
                            template + "\n", re.M)
        if len(blocks) != 1:
            raise MirrorError("Expected one preinstall imageDigestSources block")
        expressions = {
            '{{ printf "%q" .MCEMirror }}': self.dynamic_mirror("registry.redhat.io/multicluster-engine", idms),
            '{{ printf "%q" .ACMMirror }}': self.dynamic_mirror("registry.redhat.io/rhacm2", idms),
        }
        result, source, waiting = {}, None, False
        for line in blocks[0].splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("- source: "):
                if source is not None and source not in result:
                    raise MirrorError("Missing mirror")
                source = line[len("- source: "):].strip()
                if source in result or not REFERENCE.fullmatch(source):
                    raise MirrorError("Duplicate or invalid mirror source")
                waiting = False
            elif line == "mirrors:" and source is not None:
                waiting = True
            elif line.startswith("- ") and waiting and source not in result:
                value = line[2:].strip()
                match = re.fullmatch(r'{{ printf "%q" \(printf "%s(/[a-zA-Z0-9/_.-]+)" .PreinstallRegistry\) }}', value)
                if match:
                    value = self.registry + match[1]
                elif value in expressions:
                    value = expressions[value]
                elif value.startswith('"'):
                    value = json.loads(value)
                if not value.startswith(self.registry + "/") or not REFERENCE.fullmatch(value):
                    raise MirrorError("Unsupported or non-local preinstall mirror")
                result[source] = value
            else:
                raise MirrorError("Unsupported preinstall mirror syntax")
        if not result or source not in result:
            raise MirrorError("Incomplete preinstall mirrors")
        return result

    def mapped(self, repo, routes):
        if repo.startswith(self.registry + "/"):
            return repo
        for source in sorted(routes, key=len, reverse=True):
            if repo == source or repo.startswith(source + "/"):
                return routes[source] + repo[len(source):]
        raise MirrorError("Unmapped seed image repository: " + repo)

    def prepare(self):
        secret = self.oc("-n", "openshift-config", "get", "secret", "pull-secret")
        auths = json.loads(base64.b64decode(secret["data"][".dockerconfigjson"], validate=True))["auths"]
        entry = auths[self.registry]
        # Export only this registry credential, never the full hub pull secret.
        self.write("auth.json", {"auths": {self.registry: entry}})
        self.write("endpoint-auth.json", {"auths": {self.endpoint: entry}})
        self.write("idms.json", self.oc("get", "imagedigestmirrorsets.config.openshift.io"))

    def plan(self):
        template = (self.work / "template.yaml").read_text()
        source_routes = self.mappings(template, json.loads((self.work / "idms.json").read_text()))
        target_routes = self.mappings(template, json.loads((self.work / "target-idms.json").read_text()))
        lock = json.loads((self.work / "catalogs.json").read_text())
        if lock["registry"] != self.registry or lock["version"] != self.config["version"]:
            raise MirrorError("Catalog snapshot does not match this seed")
        seed = self.registry + "/ibu/seed:" + self.config["tag"]
        seed_digest = self.sha(self.raw(seed))
        pinned_seed = self.registry + "/ibu/seed@" + seed_digest
        metadata = json.loads(self.run(["skopeo", "inspect", "--no-tags", "--tls-verify=false",
                                  "--authfile", str(self.work / "auth.json"), "docker://" + pinned_seed],
                                 "Read seed metadata", 90))
        info = json.loads(metadata.get("Labels", {}).get("com.openshift.lifecycle-agent.seed_cluster_info", "{}"))
        if info.get("seed_cluster_ocp_version") != self.config["version"]:
            raise MirrorError("Seed version does not match the recorded OpenShift version")
        # Retain the seed for later replacement preinstall even if its public tag moves.
        self.copy(pinned_seed, self.registry + "/ibu/seed:ibi-" + seed_digest[7:], "auth.json")
        with tempfile.TemporaryDirectory(prefix="inventory-", dir=self.work) as scratch:
            self.run(["oc", "image", "extract", pinned_seed, "--registry-config=" + str(self.work / "auth.json"),
                 "--insecure=true", "--path=/containers.list:" + scratch], "Extract seed inventory", 1800)
            refs = list(dict.fromkeys(line.strip() for line in
                        (Path(scratch) / "containers.list").read_text().splitlines() if line.strip()))
        if not refs:
            raise MirrorError("Seed inventory is empty")
        (self.work / "report" / "containers.list").write_text("\n".join(refs) + "\n")
        images = []
        for ref in refs:
            repo, value, immutable = self.split(ref)
            source_repo, target_repo = self.mapped(repo, source_routes), self.mapped(repo, target_routes)
            tag = None
            if not immutable:
                tag = value
                snapshot = lock["catalogs"].get(source_repo + ":" + tag)
                if not snapshot:
                    raise MirrorError("Inventory tag has no pre-generation catalog snapshot: " + ref)
                value = snapshot
                self.check(source_repo + ":" + tag, value)
            self.check(source_repo + "@" + value, value)
            images.append({"reference": ref, "source": source_repo + "@" + value,
                           "target": target_repo + "@" + value, "digest": value, "catalog_tag": tag})
        self.write("plan.json", {"seed_digest": seed_digest, "version": self.config["version"],
                           "git_revision": self.config["git_revision"], "mappings": target_routes,
                           "images": images})
        print("Locked seed inventory: " + str(len(images)) + " images", flush=True)

    def transfer(self):
        plan = json.loads((self.work / "plan.json").read_text())
        seed_digest = plan["seed_digest"]
        self.check(self.endpoint + "/ibu/seed:" + self.config["tag"], seed_digest, "target-auth.json")
        results = []
        try:
            for index, item in enumerate(plan["images"], 1):
                repo = item["target"].split("@", 1)[0]
                remote_repo = self.endpoint + repo[len(self.registry):]
                retention = ":ibi-" + seed_digest[7:19] + "-" + item["digest"][7:]
                self.copy(item["source"], remote_repo + retention, "target-auth.json")
                self.check(remote_repo + "@" + item["digest"], item["digest"], "target-auth.json")
                if item["catalog_tag"]:
                    self.check(item["source"].split("@", 1)[0] + ":" + item["catalog_tag"], item["digest"])
                    self.copy(item["source"], remote_repo + ":" + item["catalog_tag"], "target-auth.json")
                    self.check(remote_repo + ":" + item["catalog_tag"], item["digest"], "target-auth.json")
                results.append({"reference": item["reference"], "status": "copied"})
                print("Copied %d/%d images (%ds)" %
                      (index, len(plan["images"]), time.monotonic() - self.started), flush=True)
            self.copy(self.registry + "/ibu/seed@" + seed_digest,
                 self.endpoint + "/ibu/seed:ibi-" + seed_digest[7:], "target-auth.json")
            self.check(self.endpoint + "/ibu/seed:" + self.config["tag"], seed_digest, "target-auth.json")
        finally:
            self.write("copy-results.json", results)

    def verify(self):
        plan = json.loads((self.work / "plan.json").read_text())
        current = self.mappings((self.work / "template.yaml").read_text(),
                           self.oc("get", "imagedigestmirrorsets.config.openshift.io"))
        if current != plan["mappings"]:
            raise MirrorError("Target preinstall mirror configuration changed")
        self.check(self.registry + "/ibu/seed:" + self.config["tag"], plan["seed_digest"])
        results = []
        try:
            for index, item in enumerate(plan["images"], 1):
                self.check(item["target"], item["digest"])
                if item["catalog_tag"]:
                    self.check(item["target"].split("@", 1)[0] + ":" + item["catalog_tag"], item["digest"])
                with tempfile.TemporaryDirectory(prefix="image-", dir=self.work) as scratch:
                    self.run(["skopeo", "--override-os", "linux", "--override-arch", "amd64", "copy",
                         "--retry-times", "2", "--authfile", str(self.work / "auth.json"),
                         "--src-tls-verify=false", "docker://" + item["target"], "dir:" + scratch],
                        "Pull target blobs for " + item["reference"], 600)
                results.append({"reference": item["reference"], "status": "passed"})
                print("Verified %d/%d images (%ds)" %
                      (index, len(plan["images"]), time.monotonic() - self.started), flush=True)
        finally:
            self.write("verify-results.json", results)
        self.write("verified.json", {"seed_digest": plan["seed_digest"], "version": plan["version"],
                               "git_revision": plan["git_revision"], "images": len(results),
                               "catalogs": sum(item["catalog_tag"] is not None for item in plan["images"])})
        print("All seed dependencies verified on target.", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "plan", "transfer", "verify"))
    parser.add_argument("directory")
    parser.add_argument("kubeconfig")
    parser.add_argument("budget", type=int)
    args = parser.parse_args(argv)
    previous_umask = os.umask(0o077)
    work = Path(args.directory)
    try:
        (work / "report").mkdir(exist_ok=True)
        # A repeated or failed stage must never leave an earlier success verdict.
        for path in (work / "verified.json", work / "report" / "verified.json"):
            path.unlink(missing_ok=True)
        images = SeedImages(work, args.kubeconfig, args.budget)
        getattr(images, args.mode)()
        return 0
    except Exception as error:
        # Unexpected parser, filesystem and API errors can contain private input.
        message = (str(error) if isinstance(error, MirrorError)
                   else "Image operation failed (" + type(error).__name__ + ")")
        failure = {"mode": args.mode, "error": message}
        try:
            for path in (work / "verified.json", work / "report" / "verified.json"):
                path.unlink(missing_ok=True)
        except OSError:
            print("Could not remove image verification report", file=sys.stderr)
        try:
            payload = json.dumps(failure, indent=2) + "\n"
            for path in (work / "failure.json", work / "report" / "failure.json"):
                temporary = path.with_suffix(".tmp")
                temporary.write_text(payload)
                temporary.replace(path)
        except OSError:
            print("Could not write image failure report", file=sys.stderr)
        print(message, file=sys.stderr)
        return 1
    finally:
        os.umask(previous_umask)


if __name__ == "__main__":
    sys.exit(main())
