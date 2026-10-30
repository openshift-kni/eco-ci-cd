"""Regression-test the day-2 worker TuneD Profile readiness check.

The convergence playbook must accept the worker's ``performance-patch-worker``
profile, not the control-plane ``performance-patch`` profile. This test reads
the actual ``worker_profile_ready`` Jinja expression from the Ansible task and
evaluates it against simulated Profile statuses: applied and not degraded is
ready; the wrong profile, an unapplied profile, or a degraded profile is not.
It does not contact a cluster or run the deployment playbook.

Run from the eco-ci-cd repository root with::

    python3 -m unittest discover -s tests -p 'test_day2_worker_tuned_profile.py' -v
"""

import unittest
from pathlib import Path

import yaml
from jinja2 import Environment


TASKS = Path(__file__).resolve().parents[1] / "playbooks/ran/tasks/check-day2-worker-convergence.yml"


class WorkerTunedProfileTest(unittest.TestCase):
    def test_worker_profile_requires_applied_not_degraded_worker_tuning(self):
        tasks = yaml.safe_load(TASKS.read_text(encoding="utf-8"))
        check = next(task for task in tasks if task["name"] == "Check worker pool and node configuration")
        expression = Environment().from_string(check["ansible.builtin.set_fact"]["worker_profile_ready"])

        for profile, applied, degraded, expected in (
            ("performance-patch-worker", "True", "False", True),
            ("performance-patch", "True", "False", False),
            ("performance-patch-worker", "False", "False", False),
            ("performance-patch-worker", "True", "True", False),
        ):
            with self.subTest(profile=profile, applied=applied, degraded=degraded):
                result = {
                    "resources": [{"status": {
                        "tunedProfile": profile,
                        "conditions": [
                            {"type": "Applied", "status": applied},
                            {"type": "Degraded", "status": degraded},
                        ],
                    }}],
                }
                self.assertEqual(
                    expression.render(worker_profile_result=result).strip() == "True", expected
                )


if __name__ == "__main__":
    unittest.main()
