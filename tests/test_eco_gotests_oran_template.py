#!/usr/bin/env python3
"""Test O-RAN eco-gotests environment rendering."""

import unittest
from pathlib import Path

try:
    from jinja2 import Environment, StrictUndefined
except ImportError:
    Environment = None


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "playbooks/ran/templates/run_eco_gotests_oran.sh.j2"


@unittest.skipIf(Environment is None, "Jinja2 is required to render templates")
class EcoGotestsOranTemplateTest(unittest.TestCase):
    def test_feature_path_and_global_labels_are_passed_unchanged(self):
        context = {
            "report_test_case_tag": "polarion-testcase-id",
            "report_parameter_tag": "polarion-parameter",
            "report_tc_prefix": "OCP-",
            "features": "oran/pre-provision",
            "labels": "!no-container",
            "hub_clusterconfigs_path": "/tmp/clusterconfigs",
            "acm_operator_namespace": "open-cluster-management",
            "hub_apps_domain_result": {"stdout": "apps.example.test"},
            "o2ims_oauth_secret_result": {"stdout": "secret"},
            "o2ims_oauth_client_id": "o2ims-client",
            "o2ims_client_cert_secret": "o2ims-client-tls-certificate",
            "o2ims_client_cert_secret_namespace": "oran-o2ims",
            "o2ims_must_gather_image": "registry.example.test/must-gather:latest",
            "eco_skip_tls_verify": "true",
            "eco_test_trace": "true",
            "eco_verbose_script": "true",
            "additional_test_env_variables": "",
            "eco_gotest_kubeconfig": "/tmp/eco-gotests-kubeconfig.yaml",
            "eco_gotests_report_path": "/tmp/eco_gotests_oran-pre-provision/report",
            "eco_gotests_image": "quay.io/ocp-edge-qe/eco-gotests",
            "eco_gotests_tag": "latest",
            "test_timeout": "12h",
        }

        rendered = Environment(undefined=StrictUndefined).from_string(
            TEMPLATE.read_text(encoding="utf-8")
        ).render(**context)

        self.assertIn('-e "ECO_TEST_FEATURES=oran/pre-provision"', rendered)
        self.assertIn('-e "ECO_TEST_LABELS=!no-container"', rendered)
        self.assertNotIn("ECO_TEST_FEATURES=oran ", rendered)


if __name__ == "__main__":
    unittest.main()
