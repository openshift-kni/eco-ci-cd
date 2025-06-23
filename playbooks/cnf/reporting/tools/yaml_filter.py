#!/usr/bin/env python3
"""
Generates playbook extra variables data file.

Tries to get everything via the command line, but if it can't, it will ask for the parameters interactively.

"""

import argparse
import io
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
# Ensure ruamel.yaml is installed
try:
    from ruamel.yaml import YAML
    from ruamel.yaml.parser import ParserError
except ImportError:
    print(
        "ruamel.yaml library is not installed. Please install it with 'python3 -m pip install -r requirements.txt' inside playbook directory",
        file=sys.stderr,
    )
    sys.exit(1)

DEL_COLLECTIONS_DEFAULT = [
    "redhatci.ocp",
]

IN_FILE_DEFAULT = "requirements.yml"
PARAMS_LIST_SEPARATOR = ","

PYYAML_DUMP_CONFIG: dict[str, any] = {
    "sort_keys": False,
    # "default_flow_style": False,
    # "default_flow_style": True,
    "indent": 2,
    "explicit_start": True,
    # "canonical": True,
}

RUAMEL_CONFIG: dict[str, Any] = {
    "mapping": 2,
    "sequence": 4,
    "offset": 2,
}
YAML_LINE_WIDTH: int = 120

# Custom representer for booleans to ensure lowercase 'true'/'false'
# def represent_bool_lowercase(dumper, data):
#     if data:
#         return dumper.represent_scalar("tag:yaml.org,2002:bool", "true")
#     return dumper.represent_scalar("tag:yaml.org,2002:bool", "false")

# for dumper in [yaml.SafeDumper, yaml.Dumper]:
#     yaml.add_representer(bool, represent_bool_lowercase, Dumper=dumper)

# extra spaces attempt (not working)
# def custom_represent_list(dumper, data):
#     return dumper.represent_sequence('tag:yaml.org,2002:seq', data)

# for dumper in [yaml.SafeDumper, yaml.Dumper]:
#     yaml.add_representer(bool, custom_represent_list, Dumper=dumper)

def comma_separated_list(arg) -> list[str]:
    """
    Validates a list of strings to be non empty.
    """
    # separate + strip white-spaces at the edges
    result = []
    for item in arg.split(PARAMS_LIST_SEPARATOR):
        if item.strip() != '':
            result.append(item)
    if not result:
        raise argparse.ArgumentTypeError(f"Failed converting {arg} into non-empty list of non-empty strings")
    return result


def run_command(command: list[str]) -> tuple[int, str, str]:
    """
    Runs an external command, collects its return code, stdout, and stderr.

    Args:
        command: A list of strings representing the command and its arguments.
                 (e.g., ["ls", "-l", "/tmp"])

    Returns:
        A tuple containing:
        - return_code (int): The exit status of the command. 0 typically means success.
        - stdout (str): The standard output of the command.
        - stderr (str): The standard error of the command.
    """
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,  # Decodes stdout/stderr as text (str)
            check=False # Do not raise CalledProcessError for non-zero exit codes
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 127, "", f"Error: Command not found: '{command[0]}'"
    except Exception as e:
        return 1, "", f"An unexpected error occurred: {e}"


def get_git_root() -> str:
    command = ["git", "rev-parse", "--show-toplevel"]
    rc, stdout, stderr = run_command(command)
    if rc != 0:
        raise RuntimeError(f"failed to run {command}, rc: {rc}, stdout: {stdout}, stderr: {stderr}")
    return stdout


def dict_filter(
    data: dict,
    container_attr: str,
    del_list: list[dict[str,str]]|None = None
) -> dict:
    """
    filters data values from container_attr by deleting items that match del_list

    Args:
        data: dict data
        container_attr: str container attribute
        del_list: list of dicts that cause item deletion

    Returns:
        The filtered data.
    """
    result: dict = data
    item: dict[str, str] = {}
    container_in = result.get(container_attr, [])
    container_out = []
    if del_list is None:
        del_list = []
    for item in container_in:
        keep = True
        for del_item in del_list:
            assert len(del_item.keys()) == 1
            del_key: str = list(del_item.keys())[0]
            del_val: str = del_item.get(del_key, None)
            item_val = item.get(del_key, None)
            if del_key in item and del_val == item_val:
                keep = False
                # need not to continue
                break
        if keep:
            container_out.append(item)
    result.update({container_attr: container_out})
    return result

def read_yaml(filename: str) -> dict:
    result = {}
    # 1. read yaml to data
    try:
        # input_file = Path(filename)
        yaml = YAML()
        with open(filename, 'r', encoding='utf-8') as ifd:
            result = yaml.load(ifd)
    except ParserError as pe:
        print(f"ERROR: File '{filename}' is not a valid YAML file: {pe}", file=sys.stderr)
        sys.exit(1)
    except Exception as re:
        print(f"ERROR: reading YAML file {filename} failed with: {re}", file=sys.stderr)
        sys.exit(1)

    return result

def yaml2str(data: dict[str, Any], config: dict[str, Any] | None = None, width: int|None = None) -> str:
    """
    Converts a dictionary to a YAML string with specific formatting.

    Args:
        data (dict): The dictionary to convert.
        config (dict): configuration for ruamel
        width (int): line width

    Returns:
        str: The formatted YAML string.
    """
    if config is None:
        config = RUAMEL_CONFIG
    if width is None:
        width = YAML_LINE_WIDTH
    yaml = YAML()
    yaml.indent(**config)
    yaml.width = width  # Or any desired width
    yaml.explicit_start = True
    string_stream = io.StringIO()
    yaml.dump(data, string_stream)
    return string_stream.getvalue()

def write_yaml(data: dict[str, Any], filename: str, config: dict[str, Any] | None = None, width: int|None = None):
    # 3. Write to YAML file
    if config is None:
        config = RUAMEL_CONFIG
    if width is None:
        width = YAML_LINE_WIDTH
    try:
        dict_as_str: str = yaml2str(data, config=config, width=width)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(dict_as_str)
    except PermissionError as pe:
        print(f"Error writing YAML file {filename}: {pe}", file=sys.stderr)
        sys.exit(1)


def parse_cli_args(args: list[str] = sys.argv[1:]):
    parser = argparse.ArgumentParser(
        description=f"Filter out {IN_FILE_DEFAULT} by removing items from container_attribute matching names",
        # Shows default values in help
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    git_root = get_git_root().strip()
    # Define command-line arguments
    # Mandatory
    parser.add_argument(
        "--in-file",
        default=os.path.join(git_root, IN_FILE_DEFAULT),
        help="source YaML data file path"
    )
    parser.add_argument(
        "--container-attr",
        dest="container_attr",
        default="collections",
        help="Attribute on which the container we clean up resides"
    )
    parser.add_argument(
        "--del-names",
        default=[""],
        type=comma_separated_list,
        help="Comma-separated list of names to clean up",
    )
    parser.add_argument(
        "--out-file",
        default=IN_FILE_DEFAULT,
        help="Output YAML file name."
    )

    return parser.parse_args(args=args)


def main():
    args = parse_cli_args(args=sys.argv[1:])
    # print(f"args: {args}")
    # 1. read yaml to data
    data = read_yaml(args.in_file)
    # 2. Filter out some keys:
    del_names = [{"name": item} for item in args.del_names]
    out_data = dict_filter(data, args.container_attr, del_list=del_names)
    # 3. Write to YAML file
    outfile = Path(args.out_file)
    # Ensure parent directory exists if --outfile is like "some/dir/file.yml"
    outfile.parent.mkdir(parents=True, exist_ok=True)
    write_yaml(out_data, args.out_file)
    print(f"Successfully transformed {args.in_file} into {args.out_file} filtering out names: {args.del_names}\n")
    print("You can use it for development file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
