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

UPLOAD_BLOCK = "Report Portal upload"
UPLOAD_GATE = "upload_to_report_portal | default(true) | bool"


def load_playbook_play(path):
    """Return the single play of a playbook."""
    plays = yaml.safe_load(path.read_text(encoding="utf-8"))
    return plays[0]


def load_playbook_tasks(path):
    """Return the play's top-level tasks, keyed by task name."""
    return {task["name"]: task for task in load_playbook_play(path)["tasks"]}


def flatten_tasks(tasks):
    """Yield every task, descending into block/rescue/always sections."""
    for task in tasks:
        yield task
        for section in ("block", "rescue", "always"):
            if section in task:
                yield from flatten_tasks(task[section])


def load_all_playbook_tasks(path):
    """Return every task, including those nested in blocks, by name."""
    return {
        task["name"]: task
        for task in flatten_tasks(load_playbook_play(path)["tasks"])
    }


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


def render_upload_command(tasks):
    """Return the upload command string declared in the playbook."""
    return tasks["Set the Report Portal upload command"]["ansible.builtin.set_fact"][
        "report_portal_upload_command"
    ]


PTP_GM_PREP_TASKS = (
    "Prepare feature suite reports",
    "Prepare the PTP ZTP cycle suite report",
    "Prepare PTP GM cycle suite reports",
)


class UploadReportPlaybookContractTest(unittest.TestCase):
    def test_upload_work_is_gated_by_one_block(self):
        block = load_playbook_tasks(PLAYBOOK)[UPLOAD_BLOCK]
        self.assertEqual(block["when"], UPLOAD_GATE)
        names = [task["name"] for task in block["block"]]
        self.assertEqual(names[0], "Require Report Portal reporting inputs")
        self.assertEqual(names[-1], "Read the Report Portal launch URL")

    def test_blocked_tasks_do_not_repeat_the_upload_gate(self):
        block = load_playbook_tasks(PLAYBOOK)[UPLOAD_BLOCK]
        for task in flatten_tasks(block["block"]):
            conditions = task.get("when")
            if conditions is None:
                continue
            conditions = conditions if isinstance(conditions, list) else [conditions]
            self.assertFalse(
                any("upload_to_report_portal" in str(c) for c in conditions),
                f"{task['name']} must rely on the enclosing block gate",
            )

    def test_launch_url_is_always_defined_for_hostvars_consumers(self):
        tasks = load_playbook_tasks(PLAYBOOK)
        block = tasks[UPLOAD_BLOCK]
        block_names = {task["name"] for task in flatten_tasks(block["block"])}
        for name in (
            "Set the Report Portal launch URL",
            "Save the Report Portal launch URL on the bastion",
            "Display the Report Portal launch URL",
        ):
            self.assertIn(name, tasks)
            self.assertNotIn(name, block_names)

    def test_upload_failure_is_the_only_explicit_result_condition(self):
        tasks = load_all_playbook_tasks(PLAYBOOK)
        upload = tasks["Upload reports to Report Portal"]
        self.assertNotIn("changed_when", upload)
        self.assertEqual(upload["failed_when"], "report_portal_upload.rc != 0")
        self.assertNotIn("no_log", upload)
        shell = upload["ansible.builtin.shell"]
        self.assertEqual(shell["cmd"], "{{ report_portal_upload_command }}")
        self.assertIn("chdir", shell)

    def test_uploader_runs_as_invoking_user_with_selinux_labels(self):
        command = render_upload_command(load_all_playbook_tasks(PLAYBOOK))
        self.assertNotIn("--security-opt label=disable", command)
        self.assertNotIn("--security-opt", command)
        self.assertNotIn("--user 0", command)
        self.assertIn("--userns=keep-id", command)
        self.assertIn('--user "$(id -u):$(id -g)"', command)
        self.assertIn(":/work:Z", command)
        self.assertIn(":ro,Z", command)
        self.assertNotIn(":z ", command)

    def test_token_is_passed_through_the_process_environment(self):
        tasks = load_all_playbook_tasks(PLAYBOOK)
        command = render_upload_command(tasks)
        self.assertIn("-e REPORTPORTAL_TOKEN", command)
        self.assertNotIn("--env-file", command)
        self.assertNotIn("REPORTPORTAL_TOKEN=", command)
        self.assertNotIn("report_portal_key", command)
        self.assertEqual(
            tasks["Upload reports to Report Portal"]["environment"],
            {"REPORTPORTAL_TOKEN": "{{ report_portal_key | trim }}"},
        )

    def test_uploader_never_writes_credentials_to_disk(self):
        text = PLAYBOOK.read_text(encoding="utf-8")
        self.assertNotIn("rpu.env", text)
        self.assertNotIn("REPORTPORTAL_TOKEN=", text)
        tasks = load_all_playbook_tasks(PLAYBOOK)
        self.assertNotIn(
            "Write Report Portal credentials for the uploader container", tasks
        )

    def test_bastion_ca_bundle_is_mounted_into_go_trust_directory(self):
        # Go reads every file under /etc/pki/tls/certs, so mounting the runner
        # bundle there adds the private CA without replacing the image roots.
        command = render_upload_command(load_all_playbook_tasks(PLAYBOOK))
        self.assertIn(
            "/etc/pki/tls/certs/runner-ca-bundle.pem:ro,Z", command
        )

    def test_timeouts_are_configurable_and_documented(self):
        play = load_playbook_play(PLAYBOOK)
        self.assertEqual(play["vars"]["report_portal_upload_timeout"], "30m")
        self.assertEqual(play["vars"]["report_portal_http_timeout"], "2m")
        command = render_upload_command(load_all_playbook_tasks(PLAYBOOK))
        self.assertIn("timeout {{ report_portal_upload_timeout }}", command)
        self.assertIn("--http-timeout {{ report_portal_http_timeout }}", command)
        text = PLAYBOOK.read_text(encoding="utf-8")
        self.assertIn("report_portal_upload_timeout          Timeout", text)
        self.assertIn("report_portal_http_timeout            HTTP timeout", text)

    def test_empty_reporter_template_name_falls_back(self):
        play = load_playbook_play(PLAYBOOK)
        self.assertIn(
            "reporter_template_name | default('Telco CI', true)",
            play["vars"]["report_portal_launch_name"],
        )

    def test_deprecated_junit_report_dir_is_reported_when_ignored(self):
        tasks = load_playbook_tasks(PLAYBOOK)
        task = tasks["Warn about the deprecated junit_report_dir argument"]
        message = task["ansible.builtin.debug"]["msg"]
        self.assertIn("junit_report_dir={{ junit_report_dir }}", message)
        self.assertIn("ignored", message)
        self.assertIn("processed_report_dir", message)
        conditions = task["when"]
        conditions = conditions if isinstance(conditions, list) else [conditions]
        self.assertIn(UPLOAD_GATE, conditions)

    def test_staging_sets_directory_and_xml_modes_separately(self):
        tasks = load_all_playbook_tasks(PLAYBOOK)
        directories = tasks["Create uploader directories"]["ansible.builtin.file"]
        self.assertEqual(directories["mode"], "0700")

        copy = tasks["Stage reports for Report Portal"]["ansible.builtin.copy"]
        self.assertNotIn("mode", copy)

        restrict = tasks["Restrict staged XML report permissions"]
        self.assertEqual(
            restrict["ansible.builtin.file"],
            {"path": "{{ item }}", "state": "file", "mode": "0600"},
        )
        staged_files = tasks["Find staged XML reports"]["register"]
        self.assertIn(f"{staged_files}.files", restrict["loop"])
        names = list(tasks)
        self.assertLess(names.index("Find staged XML reports"), names.index(restrict["name"]))

    def test_work_dir_is_removed_unless_kept_or_the_upload_failed(self):
        tasks = load_all_playbook_tasks(PLAYBOOK)
        create = tasks["Create uploader directories"]
        self.assertEqual(
            create["notify"], "Remove Report Portal uploader work directory"
        )
        recovery = tasks["Run the report-portal-uploader container"]
        self.assertIn("block", recovery)
        self.assertIn("rescue", recovery)
        rescue_names = [task["name"] for task in recovery["rescue"]]
        self.assertEqual(
            rescue_names,
            [
                "Keep the uploader work directory after a failed upload",
                "Fail the play after a failed Report Portal upload",
            ],
        )
        keep = recovery["rescue"][0]["ansible.builtin.set_fact"]
        self.assertEqual(keep, {"report_portal_keep_work_dir": True})
        failure = recovery["rescue"][1]["ansible.builtin.fail"]["msg"]
        self.assertIn("report_portal_upload.rc", failure)
        self.assertIn("report_portal_upload.stderr", failure)
        self.assertNotIn("report_portal_key", failure)
        self.assertIn(
            "not (report_portal_keep_work_dir | default(false) | bool)",
            PLAYBOOK.read_text(encoding="utf-8"),
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

    def test_keep_work_dir_no_longer_warns_about_a_credentials_file(self):
        text = PLAYBOOK.read_text(encoding="utf-8")
        self.assertNotIn(
            "WARNING: this leaves REPORTPORTAL_TOKEN in rpu.env", text
        )
        self.assertIn("never appears on the podman command line", text)

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
