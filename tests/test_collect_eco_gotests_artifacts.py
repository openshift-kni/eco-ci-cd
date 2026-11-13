#!/usr/bin/env python3
"""Tests for scripts/collect-eco-gotests-artifacts.py.

Covers testsuite renaming, JUnit gathering, k8sreporter zip exclusions,
report file preparation, and the per-suite error isolation in main().
"""

import importlib.util
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "collect-eco-gotests-artifacts.py"

JUNIT_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<testsuites name="old-top" tests="1" failures="0">\n'
    '<testsuite name="old-inner" tests="1">\n'
    '<testcase name="it works" classname="a.b"/>\n'
    '</testsuite>\n'
    '</testsuites>\n'
)


def load_script():
    """Import the dash-named script as a module."""
    spec = importlib.util.spec_from_file_location(
        "collect_eco_gotests_artifacts", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WriteXmlWithRenamedTestsuitesTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script()
        tmp = tempfile.TemporaryDirectory(prefix="eco-gotests-rename-")
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)

    def test_renames_testsuite_names_and_leaves_source_untouched(self):
        src = self.base / "report_testrun.xml"
        src.write_text(JUNIT_XML, encoding="utf-8")
        dst = self.base / "out.xml"

        self.script.write_xml_with_renamed_testsuites(str(src), str(dst), "oran-provision")

        result = dst.read_text(encoding="utf-8")
        self.assertIn('testsuites name="oran-provision"', result)
        self.assertIn('testsuite name="oran-provision"', result)
        self.assertNotIn("old-top", result)
        self.assertNotIn("old-inner", result)
        self.assertIn('<testcase name="it works"', result)
        self.assertEqual(src.read_text(encoding="utf-8"), JUNIT_XML)


class CollectionTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script()
        tmp = tempfile.TemporaryDirectory(prefix="eco-gotests-collect-")
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)

    def suite_report_dir(self, suite="oran-provision"):
        report_dir = self.base / f"eco_gotests_{suite}" / "report"
        report_dir.mkdir(parents=True, exist_ok=True)
        return report_dir

    def make_out_dirs(self):
        out = {
            "bastion_junit": self.base / "out" / "junit",
            "k8s_reporter": self.base / "out" / "k8s",
            "report_junit": self.base / "out" / "reports" / "junit",
            "report_polarion": self.base / "out" / "reports" / "polarion",
            "artifacts": self.base / "out" / "artifacts",
        }
        for path in out.values():
            path.mkdir(parents=True, exist_ok=True)
        return out

    def test_rename_and_gather_junit_xmls(self):
        report_dir = self.suite_report_dir()
        junit = report_dir / "oran_suite_test_junit.xml"
        junit.write_text(JUNIT_XML, encoding="utf-8")
        (report_dir / "other_junit_report.xml").write_text(
            '<testsuite name="other"/>\n', encoding="utf-8"
        )
        gathered = self.make_out_dirs()["bastion_junit"]

        self.script.rename_and_gather_junit_xmls(
            "oran-provision", str(report_dir), str(gathered)
        )

        # Originals are left untouched; gathered copies carry the suite name.
        self.assertEqual(junit.read_text(encoding="utf-8"), JUNIT_XML)
        copy = gathered / "oran-provision_oran_suite_test_junit.xml"
        self.assertIn('testsuites name="oran-provision"', copy.read_text(encoding="utf-8"))
        other = gathered / "oran-provision_other_junit_report.xml"
        self.assertIn('testsuite name="oran-provision"', other.read_text(encoding="utf-8"))

    def test_rename_preserves_crlf_line_endings(self):
        report_dir = self.suite_report_dir()
        junit = report_dir / "oran_suite_test_junit.xml"
        original = JUNIT_XML.replace("\n", "\r\n").encode("utf-8")
        junit.write_bytes(original)
        gathered = self.make_out_dirs()["bastion_junit"]

        self.script.rename_and_gather_junit_xmls(
            "oran-provision", str(report_dir), str(gathered)
        )

        self.assertEqual(junit.read_bytes(), original)
        copy = gathered / "oran-provision_oran_suite_test_junit.xml"
        self.assertIn(b"\r\n", copy.read_bytes())

    def test_create_k8sreporter_zip_excludes_xml_only(self):
        report_dir = self.suite_report_dir()
        (report_dir / "events.log").write_text("events\n", encoding="utf-8")
        (report_dir / "sub").mkdir()
        (report_dir / "sub" / "extra.log").write_text("extra\n", encoding="utf-8")
        (report_dir / "oran_suite_test_junit.xml").write_text(JUNIT_XML, encoding="utf-8")
        (report_dir / "oran_pods_specs.log").write_text("pod spec\n", encoding="utf-8")
        k8s_dir = self.make_out_dirs()["k8s_reporter"]

        self.script.create_k8sreporter_zip("oran-provision", str(report_dir), str(k8s_dir))

        names = zipfile.ZipFile(k8s_dir / "oran-provision_k8sreporter.zip").namelist()
        self.assertEqual(
            sorted(names), ["events.log", "oran_pods_specs.log", "sub/extra.log"]
        )

    def test_create_k8sreporter_zip_skipped_without_files(self):
        report_dir = self.suite_report_dir()
        (report_dir / "only.xml").write_text("<a/>\n", encoding="utf-8")
        k8s_dir = self.make_out_dirs()["k8s_reporter"]

        self.script.create_k8sreporter_zip("oran-provision", str(report_dir), str(k8s_dir))

        self.assertEqual(list(k8s_dir.iterdir()), [])

    def test_stage_suite_artifacts(self):
        report_dir = self.suite_report_dir()
        (report_dir / "oran_suite_test_junit.xml").write_text(JUNIT_XML, encoding="utf-8")
        (report_dir / "report_testrun.xml").write_text(
            '<testsuites name="pol-original"/>\n', encoding="utf-8"
        )
        (report_dir / "events.log").write_text("events\n", encoding="utf-8")
        out = self.make_out_dirs()

        self.script.rename_and_gather_junit_xmls(
            "oran-provision", str(report_dir), str(out["bastion_junit"])
        )
        self.script.create_k8sreporter_zip(
            "oran-provision", str(report_dir), str(out["k8s_reporter"])
        )
        self.script.stage_suite_artifacts(
            "oran-provision", str(report_dir), str(out["bastion_junit"]),
            str(out["k8s_reporter"]), str(out["artifacts"]),
        )

        suite_dir = out["artifacts"] / "junit_eco_gotests_oran-provision"
        # JUnit copy is renamed, keeps its original file name; report_testrun
        # is untouched; the zip is included and logs are not.
        junit = (suite_dir / "oran_suite_test_junit.xml").read_text(encoding="utf-8")
        self.assertIn('testsuites name="oran-provision"', junit)
        self.assertNotIn("old-top", junit)
        self.assertIn(
            'name="pol-original"',
            (suite_dir / "report_testrun.xml").read_text(encoding="utf-8"),
        )
        self.assertTrue((suite_dir / "oran-provision_k8sreporter.zip").exists())
        self.assertFalse(list(suite_dir.glob("*.log")))

    def test_prepare_report_files(self):
        report_dir = self.suite_report_dir()
        (report_dir / "report_testrun.xml").write_text(
            '<testsuites name="polarion-old"/>\n', encoding="utf-8"
        )
        (report_dir / "oran_suite_test_junit.xml").write_text(JUNIT_XML, encoding="utf-8")
        out = self.make_out_dirs()

        self.script.prepare_report_files(
            "oran-provision", str(report_dir),
            str(out["report_junit"]), str(out["report_polarion"])
        )

        polarion = out["report_junit"] / "oran-provision_suite_test_polarion.xml"
        self.assertIn('testsuites name="oran-provision"', polarion.read_text(encoding="utf-8"))
        ginkgo = out["report_polarion"] / "oran-provision_suite_test.xml"
        self.assertIn('testsuites name="oran-provision"', ginkgo.read_text(encoding="utf-8"))

    def test_prepare_report_files_uses_single_ginkgo_destination(self):
        # With several *suite_test_junit.xml matches, only the first is used
        # and a single destination file is produced.
        report_dir = self.suite_report_dir()
        for name in ("a_suite_test_junit.xml", "b_suite_test_junit.xml"):
            (report_dir / name).write_text(JUNIT_XML, encoding="utf-8")
        out = self.make_out_dirs()

        self.script.prepare_report_files(
            "oran-provision", str(report_dir),
            str(out["report_junit"]), str(out["report_polarion"])
        )

        produced = list(out["report_polarion"].glob("*.xml"))
        self.assertEqual(
            produced, [out["report_polarion"] / "oran-provision_suite_test.xml"]
        )


class MainTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script()
        tmp = tempfile.TemporaryDirectory(prefix="eco-gotests-main-")
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)

    def run_main(self, suites):
        out = self.base / "out"
        argv = [
            "collect-eco-gotests-artifacts.py",
            "--suites", suites,
            "--eco-gotest-dir-prefix", str(self.base / "eco_gotests_"),
            "--junit-dir", str(out / "junit"),
            "--k8s-reporter-dir", str(out / "k8s"),
            "--report-junit-dir", str(out / "reports" / "junit"),
            "--report-polarion-dir", str(out / "reports" / "polarion"),
            "--artifacts-dir", str(out / "artifacts"),
        ]
        with mock.patch.object(sys, "argv", argv):
            return self.script.main()

    def test_failure_in_one_suite_does_not_block_others(self):
        good = self.base / "eco_gotests_good" / "report"
        good.mkdir(parents=True)
        (good / "good_suite_test_junit.xml").write_text(JUNIT_XML, encoding="utf-8")
        (good / "report_testrun.xml").write_text(
            '<testsuites name="x"/>\n', encoding="utf-8"
        )
        (good / "events.log").write_text("log\n", encoding="utf-8")

        bad = self.base / "eco_gotests_bad" / "report"
        bad.mkdir(parents=True)
        # Invalid UTF-8 makes the in-place rename fail for this suite only.
        (bad / "bad_suite_test_junit.xml").write_bytes(b'<testsuite name="\xff\xfe"/>')

        # Stale file from a previous run must be removed by the reset.
        stale = self.base / "out" / "junit"
        stale.mkdir(parents=True)
        (stale / "stale.xml").write_text("stale\n", encoding="utf-8")

        with self.assertRaises(SystemExit) as ctx:
            self.run_main("bad good")
        self.assertEqual(ctx.exception.code, 1)

        out = self.base / "out"
        self.assertTrue((out / "junit" / "good_good_suite_test_junit.xml").exists())
        self.assertFalse((out / "junit" / "stale.xml").exists())
        self.assertTrue((out / "k8s" / "good_k8sreporter.zip").exists())
        self.assertTrue((out / "reports" / "junit" / "good_suite_test_polarion.xml").exists())
        self.assertTrue((out / "reports" / "polarion" / "good_suite_test.xml").exists())
        staged = out / "artifacts" / "junit_eco_gotests_good"
        self.assertTrue((staged / "good_suite_test_junit.xml").exists())
        self.assertTrue((staged / "report_testrun.xml").exists())
        self.assertTrue((staged / "good_k8sreporter.zip").exists())

    def test_missing_report_dir_is_skipped(self):
        self.run_main("no-such-suite")  # must not raise
        self.assertEqual(list((self.base / "out" / "junit").iterdir()), [])

    def test_oran_feature_subsuite_artifact_names(self):
        suites = {
            "oran-pre-provision": "pre_provision_suite_test_junit.xml",
            "oran-provision": "provision_suite_test_junit.xml",
        }
        for suite, junit_name in suites.items():
            # With the production prefix, these reports are
            # /tmp/eco_gotests_<suite>/report.
            report = self.base / f"eco_gotests_{suite}" / "report"
            report.mkdir(parents=True)
            (report / junit_name).write_text(JUNIT_XML, encoding="utf-8")
            (report / "report_testrun.xml").write_text(
                '<testsuites name="polarion-old"/>\n', encoding="utf-8"
            )
            (report / "events.log").write_text("events\n", encoding="utf-8")

        self.run_main(" ".join(suites))

        out = self.base / "out"
        for suite, junit_name in suites.items():
            with self.subTest(suite=suite):
                gathered = out / "junit" / f"{suite}_{junit_name}"
                self.assertTrue(gathered.is_file())
                self.assertIn(
                    f'testsuites name="{suite}"',
                    gathered.read_text(encoding="utf-8"),
                )
                self.assertTrue(
                    (out / "reports" / "junit" / f"{suite}_suite_test_polarion.xml").is_file()
                )
                self.assertTrue(
                    (out / "reports" / "polarion" / f"{suite}_suite_test.xml").is_file()
                )
                staged = out / "artifacts" / f"junit_eco_gotests_{suite}"
                self.assertTrue((staged / junit_name).is_file())
                self.assertTrue((staged / f"{suite}_k8sreporter.zip").is_file())
                self.assertEqual(
                    sorted(path.name for path in staged.iterdir()),
                    [
                        f"{suite}_k8sreporter.zip",
                        junit_name,
                        "report_testrun.xml",
                    ],
                )


if __name__ == "__main__":
    unittest.main()
