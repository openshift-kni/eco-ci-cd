#!/usr/bin/env python3
"""Exercise the Ansible cleanup tasks against a simulated Kubernetes API."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "playbooks/compute/roles/nrop_upgrades/tasks"
FAKE_MODULE = r'''
from ansible.module_utils.basic import AnsibleModule
import json

module = AnsibleModule(argument_spec={
    "kubeconfig": {"type": "str", "required": True},
    "api_version": {"type": "str"}, "kind": {"type": "str"},
    "namespace": {"type": "str"}, "name": {"type": "str"},
    "state": {"type": "str"}, "wait": {"type": "bool"},
    "wait_timeout": {"type": "int"}, "delete_options": {"type": "dict"},
})
path = module.params["kubeconfig"]
with open(path) as f:
    state = json.load(f)
kind = module.params["kind"]
state["events"].append({"action": MODE, "kind": kind, "options": module.params["delete_options"]})

def save():
    with open(path, "w") as f:
        json.dump(state, f)

if MODE == "read":
    resources = state["subscriptions"] if kind == "Subscription" else ([state["catalog"]] if state["catalog"] else [])
    save()
    module.exit_json(changed=False, resources=resources)

preconditions = module.params["delete_options"]["preconditions"]
metadata = state["catalog"]["metadata"]
if preconditions != {"uid": metadata["uid"], "resourceVersion": metadata["resourceVersion"]}:
    save()
    module.fail_json(msg="Wrong preconditions", reason="BadRequest")
attempt = sum(event["action"] == "delete" for event in state["events"])
if state["scenario"] == "non_conflict":
    save()
    module.fail_json(msg="Permission denied", reason="Forbidden")
if state["scenario"] in ("conflict", "replacement", "unlabeled", "subscription", "disappeared") and attempt == 1 or state["scenario"] == "always_conflict":
    metadata["resourceVersion"] = str(int(metadata["resourceVersion"]) + 1)
    if state["scenario"] == "replacement":
        metadata["uid"] = "replacement"
    elif state["scenario"] == "unlabeled":
        metadata["labels"] = {}
    elif state["scenario"] == "subscription":
        state["subscriptions"] = [{"spec": {"source": "test-catalog", "sourceNamespace": "openshift-marketplace"}}]
    elif state["scenario"] == "disappeared":
        state["catalog"] = None
    save()
    module.fail_json(msg="ResourceVersion changed", reason="Conflict")
state["catalog"] = None
save()
module.exit_json(changed=True)
'''


@unittest.skipUnless(shutil.which("ansible-playbook"), "ansible-playbook is required")
class StageCatalogCleanupTest(unittest.TestCase):
    def run_case(self, scenario):
        with tempfile.TemporaryDirectory(prefix="nrop-catalog-test-") as tmp:
            temp = Path(tmp)
            collection = temp / "collections/ansible_collections/kubernetes/core/plugins/modules"
            collection.mkdir(parents=True)
            for name, mode in (("k8s_info", "read"), ("k8s", "delete")):
                (collection / f"{name}.py").write_text(f"MODE = {mode!r}\n" + FAKE_MODULE)

            state_path = temp / "state.json"
            state = {
                "scenario": scenario,
                "events": [],
                "subscriptions": [],
                "catalog": {"metadata": {"uid": "original", "resourceVersion": "42", "labels": {"nrop-ci.openshift.io/temporary-catalog": "true"}}},
            }
            if scenario == "absent":
                state["catalog"] = None
            state_path.write_text(json.dumps(state))

            # Execute the actual cleanup block, not a reimplementation of it.
            stage = yaml.safe_load((TASKS / "stage_catalog.yml").read_text())
            cleanup = stage[0]["always"][0]["block"][0]
            (temp / "cleanup_stage_catalog_attempt.yml").write_text((TASKS / "cleanup_stage_catalog_attempt.yml").read_text())
            play = [{
                "hosts": "localhost", "gather_facts": False,
                "vars": {"kubeconfig": str(state_path), "nrop_stage_temp_catalog": "test-catalog",
                         "nrop_stage_temp_created": {"result": {"metadata": {"uid": "original"}}}},
                "tasks": [cleanup],
            }]
            (temp / "test.yml").write_text(yaml.safe_dump(play))
            (temp / "ansible.cfg").write_text("[defaults]\n")
            env = os.environ.copy()
            env.update(ANSIBLE_CONFIG=str(temp / "ansible.cfg"), ANSIBLE_COLLECTIONS_PATHS=str(temp / "collections"),
                       ANSIBLE_NOCOLOR="1", ANSIBLE_STDOUT_CALLBACK="default")
            result = subprocess.run(["ansible-playbook", "-i", "localhost,", "-c", "local", str(temp / "test.yml")],
                                    cwd=ROOT, env=env, capture_output=True, text=True, timeout=90)
            return result, json.loads(state_path.read_text())

    def test_cleanup_safety_and_retry(self):
        cases = {
            "success": (True, 1, 1), "absent": (True, 1, 0),
            "conflict": (True, 2, 2), "disappeared": (True, 2, 1),
            "replacement": (False, 2, 1), "unlabeled": (False, 2, 1),
            "subscription": (False, 2, 1), "non_conflict": (False, 1, 1),
            "always_conflict": (False, 5, 5),
        }
        for scenario, (success, reads, deletes) in cases.items():
            with self.subTest(scenario=scenario):
                result, state = self.run_case(scenario)
                output = result.stdout + result.stderr
                self.assertEqual(result.returncode == 0, success, output)
                self.assertEqual(sum(e["kind"] == "Subscription" for e in state["events"]), reads, output)
                self.assertEqual(sum(e["kind"] == "CatalogSource" and e["action"] == "read" for e in state["events"]), reads, output)
                self.assertEqual(sum(e["action"] == "delete" for e in state["events"]), deletes, output)
                if scenario == "conflict":
                    attempts = [e["options"]["preconditions"] for e in state["events"] if e["action"] == "delete"]
                    self.assertEqual(attempts, [{"uid": "original", "resourceVersion": "42"}, {"uid": "original", "resourceVersion": "43"}])


if __name__ == "__main__":
    unittest.main()
