#!/usr/bin/env python3
"""Tests for scripts/collect-eco-gotests-artifacts.py.

Covers testsuite renaming, the single shared report directory, k8sreporter
zip exclusions, and the per-suite error isolation in main().
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
            "report": self.base / "out" / "junit",
            "k8s_reporter": self.base / "out" / "k8s",
            "artifacts": self.base / "out" / "artifacts",
        }
        for path in out.values():
            path.mkdir(parents=True, exist_ok=True)
        return out

    def test_prepare_report_files_writes_one_renamed_copy(self):
        report_dir = self.suite_report_dir()
        junit = report_dir / "oran_suite_test_junit.xml"
        junit.write_text(JUNIT_XML, encoding="utf-8")
        (report_dir / "report_testrun.xml").write_text(
            '<testsuites name="polarion-old"/>\n', encoding="utf-8"
        )
        report_out = self.make_out_dirs()["report"]

        self.script.prepare_report_files(
            "oran-provision", str(report_dir), str(report_out)
        )

        # Originals are left untouched; the one published copy carries the
        # suite name and the lossy report_testrun aggregate is not copied.
        self.assertEqual(junit.read_text(encoding="utf-8"), JUNIT_XML)
        self.assertEqual(
            [path.name for path in report_out.iterdir()],
            ["oran-provision_suite_test.xml"],
        )
        published = (report_out / "oran-provision_suite_test.xml").read_text(
            encoding="utf-8"
        )
        self.assertIn('testsuites name="oran-provision"', published)
        self.assertIn('testsuite name="oran-provision"', published)

    def test_prepare_report_files_preserves_crlf_line_endings(self):
        report_dir = self.suite_report_dir()
        junit = report_dir / "oran_suite_test_junit.xml"
        original = JUNIT_XML.replace("\n", "\r\n").encode("utf-8")
        junit.write_bytes(original)
        report_out = self.make_out_dirs()["report"]

        self.script.prepare_report_files(
            "oran-provision", str(report_dir), str(report_out)
        )

        self.assertEqual(junit.read_bytes(), original)
        copy = report_out / "oran-provision_suite_test.xml"
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

        self.script.prepare_report_files(
            "oran-provision", str(report_dir), str(out["report"])
        )
        self.script.create_k8sreporter_zip(
            "oran-provision", str(report_dir), str(out["k8s_reporter"])
        )
        self.script.stage_suite_artifacts(
            "oran-provision", str(report_dir), str(out["report"]),
            str(out["k8s_reporter"]), str(out["artifacts"]),
        )

        suite_dir = out["artifacts"] / "junit_eco_gotests_oran-provision"
        # The published copy is renamed, the raw report is kept, report_testrun
        # is untouched, the zip is included and logs are not.
        published = (suite_dir / "oran-provision_suite_test.xml").read_text(
            encoding="utf-8"
        )
        self.assertIn('testsuites name="oran-provision"', published)
        self.assertNotIn("old-top", published)
        self.assertTrue((suite_dir / "oran_suite_test_junit.xml").exists())
        self.assertIn(
            'name="pol-original"',
            (suite_dir / "report_testrun.xml").read_text(encoding="utf-8"),
        )
        self.assertTrue((suite_dir / "oran-provision_k8sreporter.zip").exists())
        self.assertFalse(list(suite_dir.glob("*.log")))

    def test_prepare_report_files_skips_missing_ginkgo_report(self):
        report_dir = self.suite_report_dir()
        (report_dir / "report_testrun.xml").write_text(
            '<testsuites name="polarion-old"/>\n', encoding="utf-8"
        )
        out = self.make_out_dirs()

        self.script.prepare_report_files(
            "oran-provision", str(report_dir), str(out["report"])
        )

        self.assertEqual(list(out["report"].iterdir()), [])

    def test_prepare_report_files_uses_single_ginkgo_destination(self):
        # With several *suite_test_junit.xml matches, only the first is used
        # and a single destination file is produced.
        report_dir = self.suite_report_dir()
        for name in ("a_suite_test_junit.xml", "b_suite_test_junit.xml"):
            (report_dir / name).write_text(JUNIT_XML, encoding="utf-8")
        out = self.make_out_dirs()

        self.script.prepare_report_files(
            "oran-provision", str(report_dir), str(out["report"])
        )

        produced = list(out["report"].glob("*.xml"))
        self.assertEqual(
            produced, [out["report"] / "oran-provision_suite_test.xml"]
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
        self.assertTrue((out / "junit" / "good_suite_test.xml").exists())
        self.assertFalse((out / "junit" / "stale.xml").exists())
        self.assertTrue((out / "k8s" / "good_k8sreporter.zip").exists())
        self.assertFalse((out / "reports").exists())
        staged = out / "artifacts" / "junit_eco_gotests_good"
        self.assertTrue((staged / "good_suite_test.xml").exists())
        self.assertTrue((staged / "good_suite_test_junit.xml").exists())
        self.assertTrue((staged / "report_testrun.xml").exists())
        self.assertTrue((staged / "good_k8sreporter.zip").exists())

    def test_deprecated_report_junit_dir_warns(self):
        out = self.base / "out"

        with self.assertLogs(level="WARNING") as logs:
            with mock.patch.object(
                sys,
                "argv",
                [
                    "collect-eco-gotests-artifacts.py",
                    "--suites", "no-such-suite",
                    "--eco-gotest-dir-prefix", str(self.base / "eco_gotests_"),
                    "--junit-dir", str(out / "junit"),
                    "--k8s-reporter-dir", str(out / "k8s"),
                    "--artifacts-dir", str(out / "artifacts"),
                    "--report-junit-dir", str(out / "old-junit"),
                ],
            ):
                self.script.main()

        self.assertTrue(any("ignored" in message for message in logs.output))

    def test_deprecated_report_portal_dir_warns(self):
        out = self.base / "out"

        with self.assertLogs(level="WARNING") as logs:
            with mock.patch.object(
                sys,
                "argv",
                [
                    "collect-eco-gotests-artifacts.py",
                    "--suites", "no-such-suite",
                    "--eco-gotest-dir-prefix", str(self.base / "eco_gotests_"),
                    "--junit-dir", str(out / "junit"),
                    "--k8s-reporter-dir", str(out / "k8s"),
                    "--artifacts-dir", str(out / "artifacts"),
                    "--report-portal-dir", str(out / "reports" / "polarion"),
                ],
            ):
                self.script.main()

        self.assertTrue(any("ignored" in message for message in logs.output))

    def test_oran_label_runs_publish_distinct_reports(self):
        # O-RAN runs the same eco-gotests feature several times with different
        # label filters, so every run writes an identically named
        # oran_suite_test_junit.xml into its own report dir.
        features = (
            "oran-pre-provision",
            "oran-provision",
            "oran-post-provision",
            "oran-metal3-day2",
        )
        for feature in features:
            report_dir = self.base / f"eco_gotests_{feature}" / "report"
            report_dir.mkdir(parents=True)
            (report_dir / "oran_suite_test_junit.xml").write_text(
                JUNIT_XML, encoding="utf-8"
            )

        self.run_main(" ".join(features))

        out = self.base / "out" / "junit"
        self.assertEqual(
            sorted(path.name for path in out.iterdir()),
            sorted(f"{feature}_suite_test.xml" for feature in features),
        )
        for feature in features:
            content = (out / f"{feature}_suite_test.xml").read_text(encoding="utf-8")
            self.assertIn(f'testsuites name="{feature}"', content)
            self.assertIn(f'testsuite name="{feature}"', content)

    def test_duplicate_suite_names_are_rejected(self):
        with self.assertLogs(level="ERROR") as logs:
            with self.assertRaises(SystemExit) as ctx:
                self.run_main("oran-provision oran-provision")
        self.assertEqual(ctx.exception.code, 1)
        self.assertTrue(any("Duplicate suite names" in m for m in logs.output))

    def test_missing_report_dir_is_skipped(self):
        self.run_main("no-such-suite")  # must not raise
        self.assertEqual(list((self.base / "out" / "junit").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
