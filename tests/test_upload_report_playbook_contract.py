#!/usr/bin/env python3
"""Static guardrail tests for the shared Report Portal upload flow."""

from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK = ROOT / "playbooks" / "upload-report.yaml"
TEMPLATE = ROOT / "playbooks" / "templates" / "report-portal-uploader.toml.j2"
PTP_GM_PLAYBOOK = ROOT / "playbooks" / "ran" / "deploy-run-eco-gotests-ptp-gm.yaml"
PTP_PLAYBOOK = ROOT / "playbooks" / "ran" / "deploy-run-eco-gotests-ptp.yaml"
CNF_GOTESTS_PTP_GM_PLAYBOOK = (
    ROOT / "playbooks" / "ran" / "deploy-run-cnf-gotests-ptp-gm.yaml"
)


def load_playbook_tasks(path):
    """Return the tasks of the single play in a playbook, keyed by task name."""
    plays = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {task["name"]: task for task in plays[0]["tasks"]}


def load_process_play(path, name=None):
    plays = yaml.safe_load(path.read_text(encoding="utf-8"))
    for play in plays:
        if name is None or play.get("name") == name:
            if "tags" in play and play["tags"] == "process":
                return play
    raise AssertionError(f"report processing play not found in {path.name}")


def load_ptp_gm_process_play():
    return load_process_play(
        PTP_GM_PLAYBOOK, "Process PTP GM report files on bastion"
    )


def load_ptp_gm_process_tasks():
    return {task["name"]: task for task in load_ptp_gm_process_play()["tasks"]}


PTP_GM_PREP_TASKS = (
    "Prepare feature suite reports",
    "Prepare the PTP ZTP cycle suite report",
    "Prepare PTP GM cycle suite reports",
)


def upload_command(tasks):
    return tasks["Set the Report Portal upload command"]["ansible.builtin.set_fact"][
        "report_portal_upload_command"
    ]


class UploadReportPlaybookContractTest(unittest.TestCase):
    def test_credentials_are_only_required_when_upload_is_enabled(self):
        text = PLAYBOOK.read_text(encoding="utf-8")
        self.assertIn(
            "when: upload_to_report_portal | default(true) | bool",
            text.split("- name: Require Report Portal reporting inputs", 1)[1]
            .split("- name: Remove the previous Report Portal launch URL file", 1)[0],
        )

    def test_upload_failure_fails_and_success_is_the_only_changed_result(self):
        tasks = load_playbook_tasks(PLAYBOOK)
        upload = tasks["Upload reports to Report Portal"]
        self.assertEqual(
            upload["changed_when"], "report_portal_upload.rc == 0"
        )
        self.assertEqual(upload["failed_when"], "report_portal_upload.rc != 0")

    def test_container_bind_mounts_do_not_relabel_host_paths(self):
        command = upload_command(load_playbook_tasks(PLAYBOOK))
        self.assertIn("--security-opt label=disable", command)
        self.assertIn(" -v ", command)
        self.assertNotIn(":Z", command)
        self.assertNotIn(":z", command)

    def test_bastion_ca_bundle_is_mounted_into_go_trust_directory(self):
        # Go reads every file under /etc/pki/tls/certs, so mounting the runner
        # bundle there adds the private CA without replacing the image roots.
        command = upload_command(load_playbook_tasks(PLAYBOOK))
        self.assertIn(
            "/etc/pki/tls/certs/runner-ca-bundle.pem:ro", command
        )

    def test_cluster_only_work_is_gated_on_upload(self):
        tasks = load_playbook_tasks(PLAYBOOK)
        for name in (
            "Remove the previous Report Portal launch URL file",
            "Gather cluster network information",
            "Set the Report Portal launch description",
            "Initialize Report Portal launch attributes",
            "Add the cluster version attribute",
            "Add attributes collected from metrics",
        ):
            conditions = tasks[name].get("when")
            conditions = conditions if isinstance(conditions, list) else [conditions]
            self.assertTrue(
                any(c and "upload_to_report_portal" in c for c in conditions),
                f"{name} must be gated on upload_to_report_portal",
            )

    def test_default_image_is_digest_pinned_and_remains_configurable(self):
        text = PLAYBOOK.read_text(encoding="utf-8")
        self.assertRegex(
            text,
            r"report_portal_uploader_image: quay\.io/rh-ee-klaskosk/"
            r"report-portal-uploader@sha256:[0-9a-f]{64}",
        )
        self.assertIn("report_portal_uploader_tag:", text)
        self.assertIn("report_portal_uploader_reference:", text)

    def test_release_callers_and_credential_prerequisite_are_documented(self):
        text = PLAYBOOK.read_text(encoding="utf-8")
        for caller in (
            "telcov10n-functional-report",
            "telcov10n-functional-cnf-ran-report",
            "telcov10n-functional-cnf-ran-ibu-report",
            "cnf-network/cnf-reporter",
            "cnf-compute/nto/reporter",
        ):
            self.assertIn(caller, text)
        self.assertIn("must ensure those two values", text)
        self.assertIn("present in group_vars/bastions", text)

    def test_keep_work_dir_documents_that_the_token_remains(self):
        text = PLAYBOOK.read_text(encoding="utf-8")
        self.assertIn(
            "WARNING: this leaves REPORTPORTAL_TOKEN in rpu.env", text
        )

    def test_rpu_excludes_lossy_report_testrun_aggregate(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn('exclude_patterns = ["*report_testrun*"]', text)
        self.assertNotIn("exclude_patterns = []", text)
        # Nothing writes the old Polarion-converter copies any more.
        self.assertNotIn("_suite_test_polarion", text)


class BastionReportContractTest(unittest.TestCase):
    """The bastion plays publish one suite JUnit set, not two flavors of it."""

    def test_bastion_plays_use_a_single_report_directory(self):
        for path in (PTP_PLAYBOOK, PTP_GM_PLAYBOOK, CNF_GOTESTS_PTP_GM_PLAYBOOK):
            play = load_process_play(path)
            dumped = yaml.dump(play)
            self.assertIn("report_dir", play["vars"], path.name)
            self.assertNotIn("report_portal_report_dir", dumped, path.name)
            self.assertNotIn("junit_report_dir", dumped, path.name)
            self.assertNotIn("/polarion", dumped, path.name)

    def test_each_prep_task_publishes_one_suite_report(self):
        tasks = load_ptp_gm_process_tasks()
        for name in PTP_GM_PREP_TASKS:
            script = tasks[name]["ansible.builtin.shell"]
            self.assertIn("src=", script, name)
            self.assertIn('dst="{{ report_dir }}/', script, name)
            self.assertIn('> "${dst}"', script, name)
            self.assertNotIn("verify_dst", script, name)
            self.assertNotIn("cp ", script, name)

    def test_play_no_longer_reads_report_testrun_aggregate(self):
        for path in (PTP_PLAYBOOK, PTP_GM_PLAYBOOK, CNF_GOTESTS_PTP_GM_PLAYBOOK):
            self.assertNotIn("report_testrun", yaml.dump(load_process_play(path)))

    def test_eco_gotests_files_do_not_clobber_cnf_gotests_files(self):
        tasks = load_ptp_gm_process_tasks()
        for name in (
            "Remove stale eco-gotests feature report files from previous runs",
            "Remove stale eco-gotests PTP cycle report files from previous runs",
        ):
            script = tasks[name]["ansible.builtin.shell"]
            self.assertIn("report_dir", script)
            self.assertIn("/eco_", script)
        for name in PTP_GM_PREP_TASKS:
            script = tasks[name]["ansible.builtin.shell"]
            self.assertIn('dst="{{ report_dir }}/eco_', script, name)

    def test_report_directories_are_not_reset(self):
        """cnf-gotests stages into the same directory first; a reset deletes it."""
        play = load_ptp_gm_process_play()
        tasks = load_ptp_gm_process_tasks()
        self.assertNotIn("Reset the report directories", tasks)
        self.assertNotIn("state: absent", yaml.dump(play))


if __name__ == "__main__":
    unittest.main()
