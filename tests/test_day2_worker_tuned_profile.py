"""Test policy-derived day-2 worker TuneD readiness without a live cluster.

Run from the eco-ci-cd repository root with::

    python3 -m unittest discover -s tests -p 'test_day2_worker_tuned_profile.py' -v
"""

import subprocess
import unittest
from pathlib import Path

import yaml
from jinja2 import Environment

TASKS = (
    Path(__file__).resolve().parents[1]
    / "playbooks/ran/tasks/check-day2-worker-convergence.yml"
)
PLAYBOOK = (
    Path(__file__).resolve().parents[1] / "playbooks/ran/deploy-ocp-sno-day2-worker.yml"
)
WORKER_LABEL = {"machineconfiguration.openshift.io/role": "worker"}


def expression(env, template):
    """Evaluate an Ansible Jinja value expression with Jinja's native result."""
    return env.compile_expression(template.strip()[2:-2])


class WorkerTunedProfileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        play = yaml.safe_load(PLAYBOOK.read_text(encoding="utf-8"))[1]
        tasks = next(task["block"] for task in play["tasks"] if "block" in task)
        cls.tasks = {task["name"]: task for task in tasks}
        cls.task_names = [task["name"] for task in tasks]
        cls.env = Environment()
        cls.env.filters["flatten"] = lambda groups: [
            item for group in groups for item in group
        ]

    def policy(self, tuned_crs, generation=2, profiles=None):
        if profiles is None:
            profiles = [self.performance_profile("worker-profile")]
        return {
            "metadata": {
                "name": "group-du-standard-config-policy",
                "generation": generation,
            },
            "status": {"lastEvaluatedGeneration": generation},
            "spec": {
                "object-templates": [
                    {
                        "objectDefinition": {
                            "kind": "Network",
                            "metadata": {"name": "cluster"},
                            "spec": {"disableNetworkDiagnostics": True},
                        }
                    },
                    *({"objectDefinition": profile} for profile in profiles),
                    *({"objectDefinition": cr} for cr in tuned_crs),
                ]
            },
        }

    @staticmethod
    def performance_profile(name, pool="worker", node_selector=None):
        if node_selector is None:
            node_selector = {"kubernetes.io/hostname": "worker-0.example.com"}
        return {
            "kind": "PerformanceProfile",
            "metadata": {"name": name},
            "spec": {
                "machineConfigPoolSelector": {
                    f"pools.operator.machineconfiguration.openshift.io/{pool}": ""
                },
                "nodeSelector": node_selector,
            },
        }

    @staticmethod
    def tuned(name, profile, worker=True, defined=True):
        return {
            "kind": "Tuned",
            "metadata": {"name": name},
            "spec": {
                "profile": [{"name": profile}] if defined else [],
                "recommend": [
                    {
                        "profile": profile,
                        "machineConfigLabels": (
                            WORKER_LABEL
                            if worker
                            else {"machineconfiguration.openshift.io/role": "master"}
                        ),
                    }
                ],
            },
        }

    def gate_ready(self, policy):
        gate = self.tasks["Wait for the spoke to evaluate the day-2 worker policy"]
        variables = {"spoke_group_policy_result": {"resources": [policy]}}
        for name, value in gate["vars"].items():
            variables[name] = expression(self.env, value)(**variables)
        return bool(self.env.compile_expression(gate["until"])(**variables))

    def chosen_profile(self, policy):
        task = self.tasks["Record worker tuning from the evaluated day-2 policy"]
        values = task["ansible.builtin.set_fact"]
        variables = {"spoke_group_policy_result": {"resources": [policy]}}
        return {
            name: expression(self.env, value)(**variables)
            for name, value in values.items()
        }

    def test_gate_and_profile_are_derived_from_policy_not_ocp_version(self):
        for name, profile in (
            ("performance-patch", "performance-patch-worker"),  # 4.16
            ("performance-patch", "performance-patch"),  # 4.18, 4.20, 5.0
            ("ran-du-performance", "ran-du-performance"),  # 4.22 reference
            ("future-tuned", "future-worker-profile"),
        ):
            with self.subTest(profile=profile):
                policy = self.policy([self.tuned(name, profile)])
                self.assertTrue(self.gate_ready(policy))
                self.assertEqual(
                    self.chosen_profile(policy)["expected_worker_tuned_profile"],
                    profile,
                )

    def test_gate_rejects_missing_ambiguous_or_unevaluated_worker_tuning(self):
        good = self.tuned("worker-tuned", "worker-profile")
        for policy in (
            self.policy([]),
            self.policy([self.tuned("worker-tuned", "worker-profile", worker=False)]),
            self.policy([self.tuned("worker-tuned", "worker-profile", defined=False)]),
            self.policy([good, self.tuned("second-tuned", "other-worker-profile")]),
            self.policy([good], generation=2)
            | {"status": {"lastEvaluatedGeneration": 1}},
        ):
            with self.subTest(policy=policy):
                self.assertFalse(self.gate_ready(policy))

    def test_gate_waits_for_new_worker_performance_profile_before_cgu(self):
        tuned = [self.tuned("ran-du-performance", "ran-du-performance")]
        # GitOps may report Synced while the spoke still evaluates an older
        # policy with a master-only PerformanceProfile and valid worker TuneD.
        for profiles in (
            [],
            [self.performance_profile("master-profile", pool="master")],
            [self.performance_profile("worker-profile", node_selector={})],
            [
                self.performance_profile("worker-profile"),
                self.performance_profile("other-worker-profile"),
            ],
        ):
            with self.subTest(profiles=profiles):
                self.assertFalse(self.gate_ready(self.policy(tuned, profiles=profiles)))

        for selector in (
            {"node-role.kubernetes.io/worker": ""},  # existing 4.16 policy
            {"kubernetes.io/hostname": "worker-0.example.com"},  # 5.0
        ):
            with self.subTest(selector=selector):
                self.assertTrue(
                    self.gate_ready(
                        self.policy(
                            tuned,
                            profiles=[
                                self.performance_profile(
                                    "worker-profile", node_selector=selector
                                )
                            ],
                        )
                    )
                )

    def test_tuned_name_guard_rejects_policy_renames(self):
        previous = self.tasks["Record the TuneD CR names from the current group policy"]
        old_names = expression(
            self.env, previous["ansible.builtin.set_fact"]["previous_tuned_cr_names"]
        )(
            previous_group_policy_result={
                "resources": [self.policy([self.tuned("old-patch", "old-worker")])]
            }
        )
        guard = self.tasks["Require unchanged TuneD CR names across the policy switch"]
        checks = [
            self.env.compile_expression(value)
            for value in guard["ansible.builtin.assert"]["that"]
        ]
        for previous_names, day2_names, expected in (
            (old_names, old_names, True),
            (old_names, ["new-patch"], False),
            ([], old_names, False),
        ):
            with self.subTest(previous=previous_names, day2=day2_names):
                self.assertEqual(
                    all(
                        check(
                            previous_tuned_cr_names=previous_names,
                            day2_tuned_cr_names=day2_names,
                        )
                        for check in checks
                    ),
                    expected,
                )
        self.assertLess(
            self.task_names.index(
                "Require unchanged TuneD CR names across the policy switch"
            ),
            self.task_names.index(
                "Create ClusterGroupUpgrade to enforce day2 worker policies via TALM"
            ),
        )
        self.assertFalse(any("superseded TuneD" in name for name in self.task_names))

    def test_configured_lanes_keep_tuned_cr_name_across_branches(self):
        # The ZTP repository is a separate checkout and may not be present in
        # standalone eco-ci-cd CI. The runtime guard above still runs there.
        repo = PLAYBOOK.parents[3] / "ztp-site-configs-ci"
        if not (repo / ".git").exists():
            self.skipTest("ZTP repository is not checked out alongside eco-ci-cd")

        for version in ("4.14", "4.16", "4.18", "4.20", "4.22", "5.0", "5.1"):
            path = f"policygentemplates/{version}/source-crs/TunedPerformancePatch.yaml"
            names = []
            for branch in ("sno_day2_worker", "sno_day2_worker_add_worker"):
                try:
                    content = subprocess.check_output(
                        ["git", "show", f"{branch}:{path}"],
                        cwd=repo,
                        text=True,
                        stderr=subprocess.DEVNULL,
                    )
                    policy = subprocess.check_output(
                        [
                            "git",
                            "show",
                            f"{branch}:policygentemplates/{version}/acm-group-du-standard-ranGen.yaml",
                        ],
                        cwd=repo,
                        text=True,
                        stderr=subprocess.DEVNULL,
                    )
                except subprocess.CalledProcessError:
                    self.skipTest("ZTP branch refs are unavailable")
                manifests = [
                    item
                    for group in yaml.safe_load(policy)["policies"]
                    for item in group.get("manifests", [])
                    if item.get("path") == "source-crs/TunedPerformancePatch.yaml"
                ]
                self.assertEqual(len(manifests), 1)
                names.append(
                    next(
                        (
                            patch["metadata"]["name"]
                            for patch in manifests[0].get("patches", [])
                            if "name" in patch.get("metadata", {})
                        ),
                        yaml.safe_load(content)["metadata"]["name"],
                    )
                )
            with self.subTest(version=version):
                self.assertEqual(names[0], names[1])

    def test_worker_profile_requires_applied_not_degraded_worker_tuning(self):
        tasks = yaml.safe_load(TASKS.read_text(encoding="utf-8"))
        check = next(
            task
            for task in tasks
            if task["name"] == "Check worker pool and node configuration"
        )
        render = self.env.from_string(
            check["ansible.builtin.set_fact"]["worker_profile_ready"]
        )

        for required, profile, applied, degraded, expected in (
            (
                "performance-patch-worker",
                "performance-patch-worker",
                "True",
                "False",
                True,
            ),
            ("performance-patch-worker", "performance-patch", "True", "False", False),
            ("ran-du-performance", "ran-du-performance", "True", "False", True),
            ("ran-du-performance", "performance-patch-worker", "True", "False", False),
            ("future-worker-profile", "future-worker-profile", "True", "False", True),
            ("ran-du-performance", "ran-du-performance", "False", "False", False),
            ("ran-du-performance", "ran-du-performance", "True", "True", False),
        ):
            with self.subTest(
                required=required, profile=profile, applied=applied, degraded=degraded
            ):
                result = {
                    "resources": [
                        {
                            "status": {
                                "tunedProfile": profile,
                                "conditions": [
                                    {"type": "Applied", "status": applied},
                                    {"type": "Degraded", "status": degraded},
                                ],
                            }
                        }
                    ]
                }
                self.assertEqual(
                    render.render(
                        worker_profile_result=result,
                        expected_worker_tuned_profile=required,
                    ).strip()
                    == "True",
                    expected,
                )


if __name__ == "__main__":
    unittest.main()
