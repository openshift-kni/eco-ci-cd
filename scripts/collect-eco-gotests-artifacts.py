#!/usr/bin/env python3
"""Collect eco-gotests artifacts.

Handles local operations:
  - Gather JUnit XMLs to a unified directory for telcov10n-verify-junit-reports
    (testsuite names renamed to the suite name in the copies)
  - Zip k8sreporter artifacts (excluding XML files)
  - Prepare report dirs for telcov10n-functional-report
  - Stage junit_eco_gotests_<suite>/ dirs (report XMLs, the renamed JUnit copy
    and the k8sreporter zip) for the caller to fetch via SCP

Suites are eco-gotests test runs (e.g. the O-RAN runs oran-pre-provision and
oran-provision, or PTP suites like containernshide); each suite's artifacts
are read from <eco-gotest-dir-prefix><suite>/report (default:
/tmp/eco_gotests_<suite>/report).

Source report files are never modified; renames are applied to the copies
written to the output directories.

File transfers to CI artifact_dir are handled by the caller (commands.sh) via SCP.

Collection is best-effort: a failure while processing one suite is logged
and does not stop the remaining suites, but the script exits non-zero at
the end.

Usage:
    python3 collect-eco-gotests-artifacts.py \
        --suites "oran-pre-provision oran-provision" \
        --junit-dir /tmp/eco_gotests_junit \
        --k8s-reporter-dir /tmp/k8sreporter-5.0.1
"""

from argparse import ArgumentParser
from glob import glob
from logging import INFO, basicConfig, error, exception, info
from os import makedirs, walk
from os.path import basename, isdir, isfile, join, relpath
from re import sub
from shutil import copy2, rmtree
from sys import exit, stdout
from zipfile import ZIP_DEFLATED, ZipFile

basicConfig(
    level=INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=stdout,
)


def write_xml_with_renamed_testsuites(src, dst, suite):
    """Copy an XML file to dst, renaming testsuite attributes to the suite name."""
    with open(src, encoding="utf-8", newline="") as f:
        content = f.read()
    content = sub(r'(testsuites?) name="[^"]*"', rf'\1 name="{suite}"', content)
    with open(dst, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    info("Copied %s → %s", src, dst)


def rename_and_gather_junit_xmls(suite, report_dir, junit_dir):
    """Copy JUnit XMLs to the unified dir with testsuite attributes renamed.

    The original files are left untouched; only the gathered copies carry
    the suite name.
    """
    for xml_path in glob(join(report_dir, "*junit*.xml")):
        dest = join(junit_dir, f"{suite}_{basename(xml_path)}")
        write_xml_with_renamed_testsuites(xml_path, dest, suite)


def create_k8sreporter_zip(suite, report_dir, k8s_reporter_dir):
    """Zip all k8sreporter artifacts for a suite, excluding XML files."""
    files = [
        join(root, filename)
        for root, _, filenames in walk(report_dir)
        for filename in filenames
        if not filename.endswith(".xml")
    ]

    if not files:
        info("No k8sreporter files found for suite %s", suite)
        return

    zip_path = join(k8s_reporter_dir, f"{suite}_k8sreporter.zip")
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as zf:
        for file_path in files:
            zf.write(file_path, arcname=relpath(file_path, report_dir))

    info("Created %s (%d files)", zip_path, len(files))


def prepare_report_files(suite, report_dir, report_junit_dir, report_polarion_dir):
    """Copy Polarion XML and Ginkgo JUnit to report dirs with renamed testsuites.

    Dir names are crossed with their content (matches the upstream
    telcov10n-functional-report conventions):
      report_junit_dir/    → JUNIT_REPORT_PATH (Polarion report_testrun XMLs)
      report_polarion_dir/ → POLARION_REPORT_PATH (Ginkgo JUnit XMLs)
    """
    polarion_src = join(report_dir, "report_testrun.xml")
    if isfile(polarion_src):
        write_xml_with_renamed_testsuites(
            polarion_src,
            join(report_junit_dir, f"{suite}_suite_test_polarion.xml"),
            suite,
        )

    # Each suite produces a single *suite_test_junit.xml; take the first match.
    ginkgo_matches = glob(join(report_dir, "*suite_test_junit.xml"))
    if ginkgo_matches:
        write_xml_with_renamed_testsuites(
            ginkgo_matches[0],
            join(report_polarion_dir, f"{suite}_suite_test.xml"),
            suite,
        )


def stage_suite_artifacts(suite, report_dir, junit_dir, k8s_reporter_dir, artifacts_dir):
    """Stage junit_eco_gotests_<suite>/ with the former playbook's layout.

    Holds every XML from the suite's report dir (original names), the JUnit
    XML overwritten with the unified-dir copy (testsuites renamed, original
    file name restored) and the k8sreporter zip. The caller fetches the
    staged tree to the CI artifact_dir via SCP.
    """
    suite_dir = join(artifacts_dir, f"junit_eco_gotests_{suite}")
    makedirs(suite_dir, exist_ok=True)

    for xml_path in glob(join(report_dir, "*.xml")):
        copy2(xml_path, join(suite_dir, basename(xml_path)))

    for xml_path in glob(join(junit_dir, f"{suite}_*.xml")):
        copy2(xml_path, join(suite_dir, basename(xml_path)[len(suite) + 1:]))

    zip_path = join(k8s_reporter_dir, f"{suite}_k8sreporter.zip")
    if isfile(zip_path):
        copy2(zip_path, suite_dir)


def reset_directories(*paths):
    """Remove and recreate each directory."""
    for path in paths:
        rmtree(path, ignore_errors=True)
        makedirs(path, exist_ok=True)


def parse_arguments():
    parser = ArgumentParser(
        description="Collect eco-gotests artifacts on the bastion"
    )
    parser.add_argument("--suites", required=True,
                        help="Space-separated suite names; artifacts are read from "
                             "<prefix><suite>/report for each")
    parser.add_argument("--junit-dir", default="/tmp/eco_gotests_junit",
                        help="Unified JUnit directory on bastion")
    parser.add_argument("--k8s-reporter-dir", required=True,
                        help="Versioned k8sreporter directory (e.g. /tmp/k8sreporter-5.0.1)")
    parser.add_argument("--eco-gotest-dir-prefix", default="/tmp/eco_gotests_",
                        help="Bastion path prefix for suite directories")
    parser.add_argument("--report-junit-dir", default="/tmp/test_reports/junit",
                        help="Bastion dir for Polarion report_testrun XMLs (JUNIT_REPORT_PATH)")
    parser.add_argument("--report-polarion-dir", default="/tmp/test_reports/polarion",
                        help="Bastion dir for ReportPortal Ginkgo JUnit XMLs (POLARION_REPORT_PATH)")
    parser.add_argument("--artifacts-dir", default="/tmp/eco_gotests_artifacts",
                        help="Bastion dir where junit_eco_gotests_<suite>/ dirs are staged "
                             "for the caller to fetch")
    return parser.parse_args()


def main():
    args = parse_arguments()
    suites = args.suites.split()

    reset_directories(
        args.junit_dir,
        args.k8s_reporter_dir,
        args.report_polarion_dir,
        args.report_junit_dir,
        args.artifacts_dir,
    )

    failed_suites = []
    for suite in suites:
        report_dir = join(f"{args.eco_gotest_dir_prefix}{suite}", "report")
        if not isdir(report_dir):
            info("No report directory for suite %s, skipping", suite)
            continue

        info("Processing suite: %s", suite)
        try:
            rename_and_gather_junit_xmls(suite, report_dir, args.junit_dir)
            create_k8sreporter_zip(suite, report_dir, args.k8s_reporter_dir)
            prepare_report_files(
                suite, report_dir, args.report_junit_dir, args.report_polarion_dir
            )
            stage_suite_artifacts(
                suite, report_dir, args.junit_dir, args.k8s_reporter_dir, args.artifacts_dir
            )
        except Exception:
            # Best-effort collection: keep processing the remaining suites,
            # then fail the run at the end so partial artifacts are kept.
            exception("Failed to collect artifacts for suite %s", suite)
            failed_suites.append(suite)

    if failed_suites:
        error("Artifact collection failed for suite(s): %s",
              ", ".join(failed_suites))
        exit(1)

    info("Done")


if __name__ == "__main__":
    main()
