#!/usr/bin/env python3
"""Test PTP template cleanup with Jinja2 and fake command-line tools."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

try:
    from jinja2 import Environment
except ImportError:
    Environment = None


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = (
    ROOT / "playbooks/ran/templates/run_eco_gotests_ptp.j2",
    ROOT / "playbooks/ran/templates/run_eco_gotests_ptp_gm.sh.j2",
)
CRD = "hardwareconfigs.ptp.openshift.io"
FAKE_OC = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["OC_CALL_LOG"], "a") as log:
    log.write(json.dumps(args) + "\n")
if args[:2] == ["get", "crd"]:
    if os.environ.get("OC_FAILURE") == "get":
        sys.exit(2)
    if os.environ.get("OC_CRD_PRESENT") == "1":
        print("customresourcedefinition.apiextensions.k8s.io/hardwareconfigs.ptp.openshift.io")
elif args[:2] == ["-n", "openshift-ptp"] and "delete" in args:
    if os.environ.get("OC_FAILURE") == args[-1]:
        sys.exit(3)
'''
FAKE_COMMAND = "#!/bin/sh\nexit 0\n"


@unittest.skipIf(Environment is None, "Jinja2 is required to render templates")
class PtpConfigCleanupTest(unittest.TestCase):
    def render_and_run(self, template_path, present=False, failure=""):
        with tempfile.TemporaryDirectory(prefix="ptp-cleanup-test-") as tmp:
            temp = Path(tmp)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            for name, content in (("oc", FAKE_OC), ("podman", FAKE_COMMAND), ("sleep", FAKE_COMMAND)):
                command = fake_bin / name
                command.write_text(content, encoding="utf-8")
                command.chmod(0o755)
            call_log = temp / "oc-calls.jsonl"
            context = {
                "report_test_case_tag": "",
                "report_parameter_tag": "",
                "report_tc_prefix": "",
                "features": "ptp",
                "labels": "",
                "kubeconfig": str(temp / "kubeconfig"),
                "eco_gotests_image": "example/test",
                "eco_gotests_tag": "latest",
                "test_timeout": "1m",
                "eco_gotest_base_dir": str(temp / "reports"),
                "ptp_cycle_configs": [{"name": "test", "urls": ["https://example.test/config.yaml"]}],
                "spoke_kubeconfig": str(temp / "spoke-kubeconfig"),
                "eco_gotests_features": [],
                "_eco_gotests_feature_configs": [],
            }
            rendered = Environment().from_string(template_path.read_text(encoding="utf-8")).render(**context)
            script = temp / "run.sh"
            script.write_text(rendered, encoding="utf-8")
            env = os.environ.copy()
            env.update(
                PATH=f"{fake_bin}{os.pathsep}{env['PATH']}",
                OC_CALL_LOG=str(call_log),
                OC_CRD_PRESENT="1" if present else "0",
                OC_FAILURE=failure,
            )
            result = subprocess.run(["bash", str(script)], cwd=ROOT, env=env, capture_output=True, text=True)
            calls = [json.loads(line) for line in call_log.read_text().splitlines()] if call_log.exists() else []
            return result, calls

    def test_crd_presence_and_cleanup_failures(self):
        for template in TEMPLATES:
            with self.subTest(template=template.name, case="present"):
                result, calls = self.render_and_run(template, present=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                ptp_delete = calls.index(["-n", "openshift-ptp", "delete", "--all", "ptpconfigs"])
                crd_check = calls.index(["get", "crd", CRD, "--ignore-not-found", "-o", "name"])
                hardware_delete = calls.index(["-n", "openshift-ptp", "delete", "--all", CRD])
                apply = calls.index(["apply", "-f", "https://example.test/config.yaml"])
                self.assertLess(ptp_delete, crd_check)
                self.assertLess(crd_check, hardware_delete)
                self.assertLess(hardware_delete, apply)

            with self.subTest(template=template.name, case="absent"):
                result, calls = self.render_and_run(template)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn(["-n", "openshift-ptp", "delete", "--all", CRD], calls)
                self.assertLess(calls.index(["get", "crd", CRD, "--ignore-not-found", "-o", "name"]), calls.index(["apply", "-f", "https://example.test/config.yaml"]))

            for failure in ("ptpconfigs", "get", CRD):
                with self.subTest(template=template.name, case=f"failure-{failure}"):
                    result, calls = self.render_and_run(template, present=True, failure=failure)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn(["apply", "-f", "https://example.test/config.yaml"], calls)


if __name__ == "__main__":
    unittest.main()
