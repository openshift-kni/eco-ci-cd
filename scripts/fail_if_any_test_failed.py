"""
JUnit XML test result verifier with known failures support.

Processes JUnit XML reports and returns exit code 0 if all tests pass
or are known failures, exit code 1 if any unexpected failures occur.

Need to do this because of a bug in junitparser's verify subcommand 
which fails if there is only one test suite
This can be removed when https://github.com/weiwei/junitparser/pull/142 is merged

Environment Variables:
    SHARED_DIR: Directory containing XML files (default: current directory)
    KNOWN_FAILURES: JSON array of test identifiers to ignore
                   e.g., '["test1", "test2"]' or '[{"test_id": "test1"}]'

Usage:
    python fail_if_any_test_failed.py
"""

import glob
import json
import os
import sys
from typing import Dict, List, Union

from junitparser import JUnitXml, TestSuite

# Constants
SUCCESS_MESSAGE = "✅ All tests passed or were skipped"


def parse_known_failures() -> List[Union[str, Dict[str, str]]]:
    """
    Parse KNOWN_FAILURES environment variable as JSON array.
    
    Returns:
        List of known failure test identifiers.
    """
    known_failures_str = os.getenv('KNOWN_FAILURES', '[]')
    
    if not known_failures_str.strip():
        return []
    
    try:
        known_failures = json.loads(known_failures_str)
        if not isinstance(known_failures, list):
            print(f"Warning: KNOWN_FAILURES is not a list: {known_failures_str}")
            return []
        
        print(f"Known failures loaded: {len(known_failures)} test(s)")
        for failure in known_failures:
            test_id = failure.get('test_id', failure) if isinstance(failure, dict) else failure
            print(f"  - {test_id}")
        return known_failures
        
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse KNOWN_FAILURES as JSON: {e}")
        return []


def is_known_failure(test_case_name: str, 
                    known_failures: List[Union[str, Dict[str, str]]]) -> bool:
    """
    Check if test case matches any known failure (exact or partial match).
    
    Args:
        test_case_name: Name of the test case to check.
        known_failures: List of known failure identifiers.
    
    Returns:
        True if test case is a known failure.
    """
    if not known_failures:
        return False
    
    for known_failure in known_failures:
        if isinstance(known_failure, dict):
            test_id = known_failure.get('test_id', '')
        else:
            test_id = str(known_failure)
        
        if not test_id:
            continue
        
        if test_id == test_case_name or test_id in test_case_name:
            return True
    
    return False


def verify_junit_reports(directory: str) -> int:
    """
    Verify all JUnit XML reports in directory.
    
    Args:
        directory: Path to directory containing XML files.
    
    Returns:
        0 if all tests passed or were known failures, 1 otherwise.
    """
    if not os.path.exists(directory):
        print(f"Error: Directory {directory} does not exist")
        return 1
    
    if not os.path.isdir(directory):
        print(f"Error: {directory} is not a directory")
        return 1
    
    known_failures = parse_known_failures()
    
    xml_files = glob.glob(os.path.join(directory, "*.xml"))
    if not xml_files:
        print(f"Warning: No XML files found in {directory}")
        return 1
    
    print(f"Found {len(xml_files)} XML file(s) to verify:")
    for xml_file in xml_files:
        print(f"  - {os.path.basename(xml_file)}")
    
    failed_tests = 0
    skipped_known_failures = 0
    total_tests = 0
    
    for xml_file in xml_files:
        try:
            print(f"\nProcessing: {os.path.basename(xml_file)}")
            xml = JUnitXml.fromfile(xml_file)
            
            if isinstance(xml, TestSuite):
                xml = [xml]
            
            for suite in xml:
                suite_name = suite.name or "Unknown Suite"
                suite_tests = 0
                suite_failures = 0
                suite_known_failures = 0
                
                for case in suite:
                    total_tests += 1
                    suite_tests += 1
                    
                    if not case.is_passed and not case.is_skipped:
                        if is_known_failure(case.name, known_failures):
                            skipped_known_failures += 1
                            suite_known_failures += 1
                            print(f"  SKIPPED (known failure): {case.name}")
                        else:
                            failed_tests += 1
                            suite_failures += 1
                            print(f"  FAILED: {case.name}")
                
                _print_suite_status(suite_name, suite_tests, suite_failures,
                                   suite_known_failures)
                    
        except Exception as e:
            print(f"Error parsing {xml_file}: {e}")
            return 1
    
    return _print_summary_and_return_status(total_tests, failed_tests,
                                           skipped_known_failures)


def _print_suite_status(suite_name: str, suite_tests: int, 
                       suite_failures: int, suite_known_failures: int) -> None:
    """Print status summary for a test suite."""
    base_msg = f"  Suite '{suite_name}': {suite_tests} test(s)"
    
    if suite_failures == 0 and suite_known_failures == 0:
        print(f"  ✓ {base_msg} passed")
    elif suite_failures == 0:
        print(f"  ✓ {base_msg} passed ({suite_known_failures} known failures skipped)")
    else:
        failure_parts = [f"{suite_failures} failed"]
        if suite_known_failures > 0:
            failure_parts.append(f"{suite_known_failures} known failures skipped")
        print(f"  ✗ {base_msg}: {', '.join(failure_parts)}")


def _print_summary_and_return_status(total_tests: int, failed_tests: int,
                                    skipped_known_failures: int) -> int:
    """Print final summary and return exit code."""
    print(
        f"=== Summary ===\n"
        f"Total tests: {total_tests}\n"
        f"Failed tests: {failed_tests}\n"
        f"Known failures skipped: {skipped_known_failures}"
    )
    
    if failed_tests > 0:
        print(f"❌ {failed_tests} test(s) failed")
        return 1
    else:
        success_msg = SUCCESS_MESSAGE
        if skipped_known_failures > 0:
            success_msg += f" ({skipped_known_failures} known failures ignored)"
        print(success_msg)
        return 0


def main() -> int:
    """Main entry point."""
    shared_dir = os.getenv('SHARED_DIR', '.')
    return verify_junit_reports(shared_dir)


if __name__ == "__main__":
    sys.exit(main())
