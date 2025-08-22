# Copyright (C) 2024 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from __future__ import absolute_import, division, print_function
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import xml.etree.ElementTree as etree

__metaclass__ = type
__version__ = "1.0.0"

DOCUMENTATION = r"""
---
name: junit2obj
version_added: "2.0.0"
short_description: transform JUnit XML text data as dictionary retaining suites and cases structure to JSON text.
description: >
  This filter plugin transforms a string JUnit XML data to JSON
  representation of it.
  It is being implemented because 'junit2dict' filter does not
  retain suites information (timings), hence not allowing collection of
  running times as metrics for future analysis.
positional: xml_report_text
options:
  xml_report_text:
    description: The junit report xml text data
    type: str
    required: true
"""


EXAMPLES = r"""
---
- name: Convert JUnit report to a structured object
  vars:
    xml_report_text: |
      <?xml version="1.0" encoding="UTF-8"?>
      <testsuites tests="3" disabled="2" errors="0" failures="0" time="0.000426228">
          <testsuite name="Performance Addon Operator Reboot" package="/home/jenkins/workspace/CNF/cnf-compute-4.18"
              tests="3" disabled="0" skipped="2" errors="0" failures="0" time="0.000426228" timestamp="2024-12-12T20:12:23">
              <properties>
                  <property name="SuiteSucceeded" value="true"></property>
                  <property name="SuiteHasProgrammaticFocus" value="false"></property>
                  <property name="SpecialSuiteFailureReason" value=""></property>
                  <property name="SuiteLabels" value="[]"></property>
                  <property name="RandomSeed" value="1734025939"></property>
                  <property name="RandomizeAllSpecs" value="false"></property>
                  <property name="LabelFilter" value="(!openshift &amp;&amp; tier-0)"></property>
              </properties>
              <testcase name="[It] [disruptive][node][kubelet][devicemanager] Device management tests"
                  classname="Performance Addon Operator Reboot" status="skipped" time="0">
                  <skipped message="skipped"></skipped>
              </testcase>
              <testcase name="[It] [disruptive][node][kubelet][devicemanager] Device management tests [tier-3]"
                  classname="Performance Addon Operator Reboot" status="skipped" time="0">
                  <skipped message="skipped"></skipped>
              </testcase>
              <testcase name="[ReportAfterSuite] e2e serial suite"
                  classname="Performance Addon Operator Reboot" status="passed" time="6.826e-05">
                  <system-err>&gt; Enter [ReportAfterSuite] TOP-LEVEL - /home/jenkins/workspace/CNF/cnf-compute-4.18;</system-err>
              </testcase>
          </testsuite>
      </testsuites>
  ansible.builtin.debug:
    msg: "{{ xml_report_text | junit2obj }}"
# =>
# {
#     "time": 0.000426228,
#     "tests": 3,
#     "failures": 0,
#     "errors": 0,
#     "skipped": 2,
#     "test_suites": [
#         {
#             "name": "Performance Addon Operator Reboot",
#             "time": 0.0,
#             "timestamp": "2024-12-12T20:12:23",
#             "tests": 3,
#             "failures": 0,
#             "errors": 0,
#             "skipped": 2,
#             "properties": {
#                 "SuiteSucceeded": "true",
#                 "SuiteHasProgrammaticFocus": "false",
#                 "SpecialSuiteFailureReason": "",
#                 "SuiteLabels": "[]",
#                 "RandomSeed": "1734025939",
#                 "RandomizeAllSpecs": "false",
#                 "LabelFilter": "(!openshift && tier-0)"
#             },
#             "test_cases": [
#                 {
#                     "name": "[It] [disruptive][node][kubelet][devicemanager] Device management tests",
#                     "classname": "Performance Addon Operator Reboot",
#                     "time": 0.0,
#                     "result": [
#                         {
#                             "message": "skipped",
#                             "status": "skipped"
#                         }
#                     ]
#                 },
#                 {
#                     "name": "[It] [disruptive][node][kubelet][devicemanager] Device management tests [tier-3]",
#                     "classname": "Performance Addon Operator Reboot",
#                     "time": 0.0,
#                     "result": [
#                         {
#                             "message": "skipped",
#                             "status": "skipped"
#                         }
#                     ]
#                 },
#                 {
#                     "name": "[ReportAfterSuite] e2e serial suite",
#                     "classname": "Performance Addon Operator Reboot",
#                     "time": 6.826e-05,
#                     "result": [
#                         {
#                             "message": "passed",
#                             "status": "passed"
#                         }
#                     ],
#                     "system_err": "> &gt; Enter [ReportAfterSuite] TOP-LEVEL - /home/jenkins/workspace/CNF/cnf-compute-4.18;"
#                 }
#             ]
#         }
#     ]
# }
"""


RETURN = r"""
---
_value:
  description:
    - JSON data
  type: dict
"""

def _safe_int(value: Optional[str], default: int = 0) -> int:
    """Safely convert string to int with default fallback.

    Args:
        value: String value to convert
        default: Default value if conversion fails

    Returns:
        Converted integer or default value
    """
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _safe_float(value: Optional[str], default: float = 0.0) -> float:
    """Safely convert string to float with default fallback.

    Args:
        value: String value to convert
        default: Default value if conversion fails

    Returns:
        Converted float or default value
    """
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_str(value: Optional[str], default: str = "") -> float:
    """Safely convert string to float with default fallback.

    Args:
        value: String value to convert
        default: Default value if conversion fails

    Returns:
        Converted float or default value
    """
    if value is None:
        return default
    try:
        return str(value)
    except (ValueError, TypeError):
        return default

ATTR2CONVERSION = {
    "name": (_safe_str, ""),
    "timestamp": (_safe_str, time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(0))),
    "time": (_safe_float, 0.0),
    "tests": (_safe_int, 0),
    "failures": (_safe_int, 0),
    "errors": (_safe_int, 0),
    "skipped": (_safe_int, 0),
}

def _collect_failure(testcase_elem: etree.Element) -> Optional[Dict[str, Any]]:
    """Collect failure information from a test case element.

    Args:
        testcase_elem: XML element representing a test case

    Returns:
        Dictionary with failure information or None if no failure
    """
    failure_elem = testcase_elem.find("failure")
    if failure_elem is None:
        return None

    result_dict = {
        "message": failure_elem.get("message", "")
    }

    if failure_elem.text:
        result_dict["text"] = failure_elem.text

    # Preserve the raw JUnit type, but normalize the status
    result_dict["failure_type"] = failure_elem.get("type", "")
    result_dict["status"] = "failure"

    return result_dict


def _collect_error(testcase_elem: etree.Element) -> Optional[Dict[str, Any]]:
    """Collect error information from a test case element.

    Args:
        testcase_elem: XML element representing a test case

    Returns:
        Dictionary with error information or None if no error
    """
    error_elem = testcase_elem.find("error")
    if error_elem is None:
        return None

    result_dict = {
        "message": error_elem.get("message", "")
    }

    if error_elem.text:
        text = error_elem.text
        result_dict["text"] = text
        panic_indicators = ["[PANICKED]", "panic:", "PANIC"]
        is_panic = any(indicator in text for indicator in panic_indicators)
        # Check if this is actually a panicked test
        result_dict["status"] = "panicked" if is_panic else "error"
    else:
        result_dict["status"] = "error"

    return result_dict


def _collect_skipped(testcase_elem: etree.Element) -> Optional[Dict[str, Any]]:
    """Collect skipped information from a test case element.

    Args:
        testcase_elem: XML element representing a test case

    Returns:
        Dictionary with skipped information or None if not skipped
    """
    skipped_elem = testcase_elem.find("skipped")
    if skipped_elem is None:
        return None

    result_dict = {
        "message": skipped_elem.get("message", "skipped"),
        "status": "skipped"
    }

    if skipped_elem.text:
        result_dict["text"] = skipped_elem.text

    return result_dict


def _process_test_case(testcase_elem: etree.Element) -> Dict[str, Any]:
    """Process test case element into a dictionary.

    Args:
        testcase_elem: XML element representing a test case

    Returns:
        Dictionary representation of the test case
    """
    curr_case: Dict[str, Any] = {
        "name": testcase_elem.get("name", ""),
        "classname": testcase_elem.get("classname", ""),
        "time": _safe_float(testcase_elem.get("time")),
    }

    # Process test result elements (failure, error, skipped)
    result_list = []

    # Check for different result types in order of precedence
    collector_handlers: Tuple[Callable[[etree.Element], Optional[Dict[str, Any]]], ...] = (
        _collect_failure,
        _collect_error,
        _collect_skipped,
    )

    for handler in collector_handlers:
        curr_elem = handler(testcase_elem)
        if curr_elem is not None:
            result_list.append(curr_elem)
            break

    # If no specific result, assume passed
    if not result_list:
        result_list.append({
            "message": "passed",
            "status": "passed",
        })

    curr_case["result"] = result_list

    # Handle system-err and system-out
    system_err = testcase_elem.find("system-err")
    if system_err is not None and system_err.text:
        curr_case["system_err"] = system_err.text

    system_out = testcase_elem.find("system-out")
    if system_out is not None and system_out.text:
        curr_case["system_out"] = system_out.text

    return curr_case


def _process_test_suite(testsuite_elem: etree.Element) -> Dict[str, Any]:
    """Process test suite element into a dictionary.

    Args:
        testsuite_elem: XML element representing a test suite

    Returns:
        Dictionary representation of the test suite
    """
    curr_suite = {}
    for attr, (converter, _default) in ATTR2CONVERSION.items():
        if attr in {"name", "timestamp", "time"}:
            # Read name, timestamp, and time from XML (time includes setup/teardown)
            curr_suite[attr] = converter(testsuite_elem.get(attr), default=_default)
            continue
        # Initialize counters to zero (will be calculated from test cases)
        curr_suite[attr] = _default

    # Process properties - always include properties section
    properties_elem = testsuite_elem.find("properties")
    properties = {}
    if properties_elem is not None:
        for prop_elem in properties_elem.findall("property"):
            prop_name = prop_elem.get("name", "")
            prop_value = prop_elem.get("value", "")
            properties[prop_name] = prop_value
    curr_suite["properties"] = properties

    # Process test cases
    test_cases = []
    for testcase_elem in testsuite_elem.findall("testcase"):
        test_case = _process_test_case(testcase_elem)
        test_cases.append(test_case)
        status = test_case.get("result", [{}])[0].get("status", "passed")
        if status == "failure":
            curr_suite["failures"] += 1
        elif status in ("error", "panicked"):
            curr_suite["errors"] += 1
        elif status == "skipped":
            curr_suite["skipped"] += 1
        # Note: suite time is read from XML (includes setup/teardown), not calculated from test cases
        curr_suite["tests"] += 1

    curr_suite["test_cases"] = test_cases

    return curr_suite


class FilterModule:
    """Filter module for converting JUnit XML reports to JSON."""

    def filters(self) -> Dict[str, Any]:
        """Return available filters.

        Returns:
            Dictionary mapping filter names to filter functions
        """
        return {
            "junit2obj": self.junit2obj,
        }

    def junit2obj(self, junit_report_text: str) -> Dict[str, Any]:
        """Convert JUnit XML Report into JSON using xml.etree.ElementTree.

        Args:
            junit_report_text: String containing JUnit XML report

        Returns:
            Dictionary representation of the JUnit report

        Raises:
            ValueError: If XML is invalid or has unexpected structure
        """
        if not isinstance(junit_report_text, str):
            raise ValueError("Input must be a string")

        if not junit_report_text.strip():
            raise ValueError("Input XML cannot be empty")

        # Parse XML
        try:
            root = etree.fromstring(junit_report_text.encode('utf-8'))
        except etree.ParseError as exc:
            raise ValueError(f"Invalid XML: {exc}") from exc

        # Process test suites
        test_suites = []
        elements = root.findall("testsuite") if root.tag == "testsuites" else [root]
        test_suites = [_process_test_suite(testsuite_elem) for testsuite_elem in elements]

        # Build report structure
        report = {
            "test_suites": test_suites,
            "schema_version": __version__,
        }

        # Use hybrid approach: prefer XML top-level values, fallback to calculated from suites
        for attr in set(ATTR2CONVERSION.keys()) - {"name", "timestamp"}:
            converter, _default = ATTR2CONVERSION[attr]
            xml_value = root.get(attr)
            if xml_value is None:
                # Calculate from test suites if not in XML
                report[attr] = sum(converter(suite.get(attr, None), default=_default) for suite in test_suites)
                continue
            # Use value from XML if available
            report[attr] = converter(xml_value)

        return report
