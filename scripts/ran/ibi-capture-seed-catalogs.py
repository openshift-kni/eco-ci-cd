#!/usr/bin/env python3
"""Capture and retain the running seed catalogs before seed generation."""

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


class CaptureError(RuntimeError):
    """An error that is safe to report without command output or credentials."""


def run(args, timeout=120):
    """Run a tool without forwarding its potentially sensitive output on failure."""
    try:
        result = subprocess.run(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        raise CaptureError(args[0] + " timed out") from None
    except OSError:
        raise CaptureError(args[0] + " could not be executed") from None
    if result.returncode:
        raise CaptureError(args[0] + " failed (exit " + str(result.returncode) + ")")
    return result.stdout


def get(kubeconfig, *args):
    return json.loads(run([
        "oc", "--kubeconfig", kubeconfig, "--request-timeout=60s", *args, "-o", "json",
    ]))


def repository(ref):
    ref = ref.split("@", 1)[0]
    return ref.rsplit(":", 1)[0] if ":" in ref.rsplit("/", 1)[-1] else ref


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def capture(spoke, hub, registry, version, scratch_parent=None):
    """Return the existing catalog handoff schema after all checks succeed."""
    if not re.fullmatch(r"[a-zA-Z0-9.-]+:[0-9]+", registry):
        raise CaptureError("Invalid mirror registry")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+([-.][0-9A-Za-z.-]+)?", version):
        raise CaptureError("Invalid seed version")

    catalogs = get(spoke, "get", "catalogsources.operators.coreos.com", "-A")["items"]
    pods = get(spoke, "get", "pods", "-A", "-l", "olm.catalogSource")["items"]
    secret = get(hub, "-n", "openshift-config", "get", "secret", "pull-secret")
    auths = json.loads(base64.b64decode(secret["data"][".dockerconfigjson"], validate=True))["auths"]
    snapshots = {}
    with tempfile.TemporaryDirectory(prefix="ibi-catalogs.", dir=scratch_parent) as scratch:
        auth = Path(scratch) / "auth.json"
        with os.fdopen(os.open(auth, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
            json.dump({"auths": {registry: auths[registry]}}, stream)

        def raw(ref):
            return run([
                "skopeo", "inspect", "--raw", "--tls-verify=false",
                "--authfile", str(auth), "docker://" + ref,
            ])

        for catalog in catalogs:
            ref = catalog.get("spec", {}).get("image", "")
            if not ref.startswith(registry + "/") or "@" in ref:
                continue
            if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9./_:-]*", ref):
                raise CaptureError("Invalid catalog reference")
            if ":" not in ref.rsplit("/", 1)[-1]:
                ref += ":latest"
            manifest = raw(ref)
            captured = digest(manifest)
            allowed = {captured}
            index = json.loads(manifest)
            if "manifests" in index:
                children = [entry["digest"] for entry in index["manifests"]
                            if entry.get("platform", {}).get("os") == "linux"
                            and entry.get("platform", {}).get("architecture") == "amd64"]
                if len(children) != 1 or digest(raw(repository(ref) + "@" + children[0])) != children[0]:
                    raise CaptureError("Catalog lacks a verified linux/amd64 manifest")
                allowed.add(children[0])
            meta = catalog["metadata"]
            matches = [pod for pod in pods
                       if pod["metadata"]["namespace"] == meta["namespace"]
                       and pod["metadata"].get("labels", {}).get("olm.catalogSource") == meta["name"]
                       and not pod["metadata"].get("deletionTimestamp")]
            if len(matches) != 1:
                raise CaptureError("Expected one active seed catalog Pod")
            pod = matches[0]
            if not any(c.get("type") == "Ready" and c.get("status") == "True"
                       for c in pod.get("status", {}).get("conditions", [])):
                raise CaptureError("Seed catalog Pod is not Ready")
            names = {c["name"] for c in pod["spec"]["containers"] if repository(c["image"]) == repository(ref)}
            statuses = [s for s in pod.get("status", {}).get("containerStatuses", [])
                        if s["name"] in names and s.get("ready")]
            image_id = statuses[0].get("imageID", "") if len(statuses) == 1 else ""
            match = re.search(r"(sha256:[a-f0-9]{64})$", image_id)
            if not match or match.group(1) not in allowed:
                raise CaptureError("Running catalog differs from registry snapshot")
            retained = repository(ref) + ":ibi-catalog-" + captured[7:]
            run([
                "skopeo", "copy", "--all", "--preserve-digests",
                "--authfile", str(auth), "--src-tls-verify=false", "--dest-tls-verify=false",
                "docker://" + repository(ref) + "@" + captured, "docker://" + retained,
            ], 600)
            if digest(raw(ref)) != captured or digest(raw(retained)) != captured:
                raise CaptureError("Catalog changed during snapshot")
            if ref in snapshots and snapshots[ref] != captured:
                raise CaptureError("Conflicting catalog snapshots")
            snapshots[ref] = captured
    if not snapshots:
        raise CaptureError("No local seed catalog tags were captured")
    return {"registry": registry, "version": version, "catalogs": snapshots}


def write_snapshot(output, snapshot):
    """Publish complete JSON by replacing a file on the same filesystem."""
    output = Path(output)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=output.parent, prefix=".catalogs-", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(snapshot, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spoke_kubeconfig")
    parser.add_argument("hub_kubeconfig")
    parser.add_argument("registry")
    parser.add_argument("version")
    parser.add_argument("output")
    args = parser.parse_args(argv)
    try:
        output = Path(args.output)
        if not output.is_absolute():
            raise CaptureError("Catalog output must be an absolute file path")
        output.unlink(missing_ok=True)
        snapshot = capture(
            args.spoke_kubeconfig, args.hub_kubeconfig, args.registry, args.version,
            scratch_parent=output.parent,
        )
        write_snapshot(output, snapshot)
    except CaptureError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError):
        print("Catalog capture failed: invalid input, response, or output file", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
