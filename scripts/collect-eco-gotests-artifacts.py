#!/usr/bin/env python3
"""Collect eco-gotests artifacts.

Handles local operations:
  - Publish one Ginkgo suite JUnit XML per suite into the shared report
    directory (testsuite names renamed to the suite name). That single
    directory is both the rpu input and the JUnit verification input
  - Zip k8sreporter artifacts (excluding XML files)
  - Stage junit_eco_gotests_<suite>/ dirs (report XMLs, the renamed suite copy
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
from logging import INFO, basicConfig, error, exception, info, warning
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


def prepare_report_files(suite, report_dir, report_out_dir):
    """Publish the suite's Ginkgo JUnit report to the shared report directory.

    Only the raw Ginkgo JUnit report is written; the lossy Polarion
    report_testrun aggregate is never copied. One file per suite keeps rpu
    from counting the same specs twice.

    The destination is keyed by the suite name, not by the source basename.
    That matters for O-RAN, where the same eco-gotests feature runs several
    times with different label filters and every run writes an identically
    named ``oran_suite_test_junit.xml`` into its own report dir.
    """
    # Each suite produces a single *suite_test_junit.xml; take the first match.
    ginkgo_matches = glob(join(report_dir, "*suite_test_junit.xml"))
    if ginkgo_matches:
        write_xml_with_renamed_testsuites(
            ginkgo_matches[0],
            join(report_out_dir, f"{suite}_suite_test.xml"),
            suite,
        )


def stage_suite_artifacts(suite, report_dir, junit_dir, k8s_reporter_dir, artifacts_dir):
    """Stage junit_eco_gotests_<suite>/ for the caller to fetch via SCP.

    Holds every XML from the suite's report dir (original names), the renamed
    suite report published to the shared report directory and the k8sreporter
    zip.
    """
    suite_dir = join(artifacts_dir, f"junit_eco_gotests_{suite}")
    makedirs(suite_dir, exist_ok=True)

    for xml_path in glob(join(report_dir, "*.xml")):
        copy2(xml_path, join(suite_dir, basename(xml_path)))

    suite_report = join(junit_dir, f"{suite}_suite_test.xml")
    if isfile(suite_report):
        copy2(suite_report, join(suite_dir, basename(suite_report)))

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
                        help="Space-separated, unique suite names; artifacts are read "
                             "from <prefix><suite>/report for each. The suite name keys "
                             "the published report, so repeated runs of the same "
                             "feature (e.g. O-RAN label filters) stay separate")
    parser.add_argument("--junit-dir", default="/tmp/eco_gotests_junit",
                        help="Unified JUnit directory on bastion")
    parser.add_argument("--k8s-reporter-dir", required=True,
                        help="Versioned k8sreporter directory (e.g. /tmp/k8sreporter-5.0.1)")
    parser.add_argument("--eco-gotest-dir-prefix", default="/tmp/eco_gotests_",
                        help="Bastion path prefix for suite directories")
    # Accepted for compatibility with older callers; the suite reports are
    # written to --junit-dir now.
    parser.add_argument("--report-portal-dir", "--report-polarion-dir",
                        dest="report_portal_dir", default=None,
                        help="Deprecated and ignored; suite reports go to --junit-dir")
    # Accepted for compatibility with older callers; Polarion reporting is gone.
    parser.add_argument("--report-junit-dir", default=None,
                        help="Deprecated and ignored; Polarion reporting was removed")
    parser.add_argument("--artifacts-dir", default="/tmp/eco_gotests_artifacts",
                        help="Bastion dir where junit_eco_gotests_<suite>/ dirs are staged "
                             "for the caller to fetch")
    return parser.parse_args()


def main():
    args = parse_arguments()
    if args.report_junit_dir is not None:
        warning(
            "--report-junit-dir=%s is deprecated and ignored; "
            "suite reports go to --junit-dir",
            args.report_junit_dir,
        )

    if args.report_portal_dir is not None:
        warning(
            "--report-portal-dir=%s is deprecated and ignored; "
            "suite reports go to --junit-dir",
            args.report_portal_dir,
        )

    suites = args.suites.split()
    duplicates = sorted({suite for suite in suites if suites.count(suite) > 1})
    if duplicates:
        error(
            "Duplicate suite names in --suites (%s); each run needs a unique "
            "name because all runs publish into the same report directory",
            ", ".join(duplicates),
        )
        exit(1)

    reset_directories(
        args.junit_dir,
        args.k8s_reporter_dir,
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
            prepare_report_files(suite, report_dir, args.junit_dir)
            create_k8sreporter_zip(suite, report_dir, args.k8s_reporter_dir)
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
