#!/usr/bin/env python3

import pytest
from . import yaml_filter



def test_yaml_filter_found_key():
    input_data = {
        "collections": [
            {
                "name": "abc.efg",
                "version": "1.0.0",
            },
        ],
    }
    del_list = [{"name": "abc.efg"}]
    expected = {"collections": []}
    actual = yaml_filter.dict_filter(input_data, "collections", del_list=del_list)
    assert expected == actual

def test_yaml_filter_miss_key():
    input_data = {
        "collections": [
            {
                "name": "abc.efg",
                "version": "master",
            },
        ],
    }
    del_list = [{"name": "abc.effect"}]
    expected = input_data
    actual = yaml_filter.dict_filter(input_data, "collections", del_list=del_list)
    assert expected == actual

def test_yaml_filter():
    input_data = {
        "collections": [
            {
                "name": "abc.efg",
                "version": "0.1.0",
            },
            {
                "name": "das.bass",
                "version": "master",
            },
        ],
    }
    del_list = [{"name": "abc.efg"}, {"name": "das.bass"}]
    expected = {"collections": []}
    actual = yaml_filter.dict_filter(input_data, "collections", del_list=del_list)
    assert expected == actual

def test_yaml2str():
    data = {
        "a": [
            "b",
            "c",
            "d",
        ]
    }
    expected: str = """---
a:
  - b
  - c
  - d
"""
    actual: str = yaml_filter.yaml2str(data)    
    assert actual == expected