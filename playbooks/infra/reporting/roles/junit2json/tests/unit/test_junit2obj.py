#
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
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type
import json
import os
import pytest
from importlib import import_module

# Try importing junit2obj from multiple possible locations
junit2obj = None
import_attempts = [
    "ansible_collections.redhatci.ocp.plugins.filter.junit2obj",
    "plugins.filter.junit2obj", 
    "filter_plugins.junit2obj"
]

for module_path in import_attempts:
    try:
        junit2obj = import_module(module_path)
        break
    except (ImportError, ModuleNotFoundError):
        continue

if junit2obj is None:
    raise ImportError("junit2obj not found in any of the expected locations") from None


# Calculate test data directory based on this test file's location
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(TEST_DIR, "data")


def get_test_data_path(filename):
    """Get absolute path to test data file"""
    return os.path.join(DATA_DIR, filename)


@pytest.fixture
def input_data(request):  # type: ignore
    file_path: str = str(request.param)  # type: ignore
    with open(file_path, "r") as fd:
        return fd.read()


@pytest.fixture
def expected_data_object(request):  # type: ignore
    file_path: str = str(request.param)  # type: ignore
    with open(file_path, "r") as fd:
        return json.loads(fd.read())


@pytest.mark.parametrize(
    "input_data,expected_data_object",
    [
        (
            get_test_data_path("test_junit2obj_simple_single_input.xml"),
            get_test_data_path("test_junit2obj_simple_result.json"),
        ),
        (
            get_test_data_path("test_junit2obj_simple_input.xml"),
            get_test_data_path("test_junit2obj_simple_result.json"),
        ),
        (
            get_test_data_path("test_junit2obj_failure_input.xml"),
            get_test_data_path("test_junit2obj_failure_result.json"),
        ),
        (
            get_test_data_path("test_junit2obj_complex_input.xml"),
            get_test_data_path("test_junit2obj_complex_result.json"),
        ),
    ],
    indirect=True,
)
def test_simple_data_object_true(input_data, expected_data_object):  # type: ignore
    filter = junit2obj.FilterModule()
    actual: str = filter.filters()["junit2obj"](input_data)  # type: ignore
    assert expected_data_object == actual
