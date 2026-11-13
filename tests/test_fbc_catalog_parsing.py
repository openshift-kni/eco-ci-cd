"""Verify FBC catalog parsing with quoted and unquoted timestamps.

The PTP 5.1 catalog can contain an unquoted ``createdAt`` value that YAML parses
as a datetime. With older Ansible templating, this value can cause the parsed
document list to be stored as text, preventing package detection.

This test runs the production parsing task against both timestamp formats:
quoted and unquoted. It verifies that the task returns a list of documents,
identifies the PTP package, and represents ``createdAt`` as a string.

Run from the repository root:
    python3 -m unittest discover -s tests -p 'test_fbc_catalog_parsing.py' -v
"""

import base64
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
FBC_TASKS = ROOT / "playbooks/roles/ocp_operator_mirror/tasks/mirror_from_fbc.yaml"


@unittest.skipUnless(shutil.which("ansible-playbook"), "ansible-playbook is required")
class FbcCatalogParsingTest(unittest.TestCase):
    def test_quoted_and_unquoted_timestamps(self):
        """Verify that the parsing task handles both PTP timestamp formats."""
        tasks = yaml.safe_load(FBC_TASKS.read_text(encoding="utf-8"))
        extraction = next(task for task in tasks if task["name"] == "Extract bundle from catalog (generation mode or no bundle digest)")
        parse_task = next(task for task in extraction["block"] if task["name"] == "Parse catalog file into documents")

        for timestamp in ("'2026-10-21T03:53:13Z'", "2025-09-10 10:13:05"):
            with self.subTest(timestamp=timestamp), tempfile.TemporaryDirectory() as tmp:
                catalog = f"""---
schema: olm.package
name: ptp-operator
---
schema: olm.channel
name: stable
package: ptp-operator
---
schema: olm.bundle
name: ptp-operator.v5.1.0
package: ptp-operator
properties:
  - value:
      annotations:
        createdAt: {timestamp}
"""
                playbook = [{
                    "hosts": "localhost",
                    "gather_facts": False,
                    "tasks": [
                        {"ansible.builtin.set_fact": {"cat": {"content": base64.b64encode(catalog.encode()).decode()}}},
                        parse_task,
                        {"ansible.builtin.assert": {"that": [
                            "docs | type_debug == 'list'",
                            "docs | length == 3",
                            "docs | selectattr('schema', 'equalto', 'olm.package') | map(attribute='name') | first == 'ptp-operator'",
                            "docs[2].properties[0].value.annotations.createdAt is string",
                        ]}},
                    ],
                }]
                path = Path(tmp) / "test.yml"
                path.write_text(yaml.safe_dump(playbook), encoding="utf-8")
                config = Path(tmp) / "ansible.cfg"
                config.write_text("[defaults]\nstdout_callback = default\n", encoding="utf-8")
                result = subprocess.run(
                    ["ansible-playbook", "-i", "localhost,", "-c", "local", str(path)],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                    env={**os.environ, "ANSIBLE_CONFIG": str(config)},
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
