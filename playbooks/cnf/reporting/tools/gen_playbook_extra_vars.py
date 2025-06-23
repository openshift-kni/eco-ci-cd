#!/usr/bin/env python3
"""
Generates playbook extra variables data file.

Tries to get everything via the command line, but if it can't, it will ask for the parameters interactively.

"""

import argparse
import getpass
import json
import os
import socket
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import urllib.parse
import xml.etree.ElementTree as ET
from . import yaml_filter

SUPPORTED_CI_NAMES = [
    "dci",
    "github",
    "gitlab",
    "jenkins",
    "prow",
]


SUPPORTED_DATA_FORMATS = [
    "xml",
    "json",
    "yaml",
    "txt"
]

TEMPLATE_DEFAULT = "templates/test_report_send.yml.j2"


RUAMEL_CONFIG: dict[str, Any] = {
    "mapping": 2,
    "sequence": 4,
    "offset": 2,
}
YAML_LINE_WIDTH: int = 120

DEFAULTS = {
    "output_dir": os.getcwd(),
    "outfile": "data.yml",
    "trs_ci_system": "dci",
    "reports_list": [],
    "splunk_url": None,
    "splunk_token": None,
    "splunk_channel": None,
    "splunk_index": None,
    "trs_metadata_path": None,
}


def tpl2pb(filename: str = TEMPLATE_DEFAULT) -> str:
    """
    Converts a Jinja2 template file name to the corresponding playbook file name.

    Args:
        filename: The Jinja2 template file name.

    Returns:
        The playbook file name.
    """
    return os.path.basename(filename).replace(".j2", "")


def comma_separated_list(arg) -> list[str]:
    """
    Validates a list of strings to be non empty, by splitting and stripping whitespaces.

    Args:
        arg: string representing comma-separated list of items

    Raises:
        argparse.ArgumentTypeError if the list is empty,  is raised
    Returns:
        resulting list of strings
    """
    # separate + strip white-spaces at the edges
    result = []
    for item in arg.split(","):
        if item.strip() == "":
            continue
        result.append(item)
    if None in result or "" in result:
        raise argparse.ArgumentTypeError(
            f"Failed converting {arg} into non-empty list of non-empty strings"
        )
    return result


def str_url_validator(item_url_str: str, comment: str = "URL") -> str:
    """
    Validates if the given string is a syntactically valid and DNS-resolvable URL.
    Suitable for use as an argparse type.

    Args:
        item_url_str: The string to validate.
        comment: optional str for errors
    Returns:
        The item_url_str if it's a valid and resolvable URL.

    Raises:
        argparse.ArgumentTypeError: If the string is not a valid or resolvable URL.
    """
    # 1. Check if the input is a string
    if not isinstance(item_url_str, str):
        raise argparse.ArgumentTypeError(
            f"{comment} - must be a string, got {type(item_url_str)}."
        )

    # 2. Parse the URL
    # urlparse is generally lenient and rarely raises errors for string inputs,
    # so we check its components.
    try:
        parsed_url = urllib.parse.urlparse(item_url_str)
    except Exception as e:
        # Catch any unexpected error during parsing, though unlikely for urlparse with strings.
        raise argparse.ArgumentTypeError(
            f"{comment} Could not be parsed as URL '{item_url_str}': {e}"
        )

    # 3. Validate essential URL components
    if not parsed_url.scheme:
        raise argparse.ArgumentTypeError(
            f"{comment}: '{item_url_str}' is missing a scheme (e.g., 'http', 'https')."
        )

    if not parsed_url.netloc:
        # This covers cases like "http://" where netloc is empty,
        # or if the URL has no authority part.
        raise argparse.ArgumentTypeError(
            f"{comment}: '{item_url_str}' is missing a network location (e.g., domain name or IP address)."
        )

    # parsed_url.hostname correctly extracts the hostname part from netloc,
    # stripping the port if present. It will be None if netloc is empty or invalid.
    hostname = parsed_url.hostname
    if not hostname:
        # This catches cases where netloc might be present but doesn't yield a valid hostname
        # (e.g., "http://:80" or other malformed netlocs).
        raise argparse.ArgumentTypeError(
            f"{comment}: '{item_url_str}' has an invalid or missing hostname component in its network location ('{parsed_url.netloc}')."
        )

    # 4. Attempt to resolve the hostname via DNS
    try:
        socket.gethostbyname(hostname)
    except socket.gaierror:
        # gaierror is raised for address-related errors, including DNS lookup failure.
        raise argparse.ArgumentTypeError(
            f"{comment}: Hostname '{hostname}' (from '{item_url_str}') could not be resolved (DNS lookup failed)."
        )
    except socket.error as e:
        # Catch other potential socket errors during resolution that aren't gaierror.
        raise argparse.ArgumentTypeError(
            f"{comment}: A network-related error occurred while trying to resolve hostname '{hostname}' (from '{item_url_str}'): {e}"
        )

    # If all checks pass, return the original URL string
    return item_url_str


def str_uuid_validator(uuid_string: str, comment: str = "UUID validation") -> str:
    """
    Validates if the given string is a syntactically valid UUID and
    is formatted exactly as a standard lowercase, hyphenated UUID.
    (e.g., 'cb16bd3a-7a90-43fe-a222-fa588efe029d').

    Suitable for use as an argparse type.

    Args:
        uuid_string: The string to validate.
        comment: cli variable comment

    Returns:
        The uuid_string if it's a valid and correctly formatted UUID.

    Raises:
        argparse.ArgumentTypeError: If the string is not a valid or
                                     correctly formatted UUID.
    """
    if not isinstance(uuid_string, str):
        raise argparse.ArgumentTypeError(
            f"{comment} Invalid type: UUID input must be a string, got {type(uuid_string)}."
        )

    try:
        # Attempt to parse the string as a UUID.
        # The uuid.UUID() constructor is flexible about the input format it accepts
        # (e.g., it can handle uppercase, missing hyphens, braces).
        parsed_uuid = uuid.UUID(uuid_string)

        # Now, check if the original input string is *exactly* the same as
        # the canonical string representation of the parsed UUID.
        # str(parsed_uuid) always returns the UUID in lowercase, hyphenated format.
        # This ensures the input was not only a valid UUID structure but also
        # already in the precise required format.
        if str(parsed_uuid) == uuid_string:
            return uuid_string
        # The input was a valid UUID structure but not in the exact
        # lowercase, hyphenated format required. For example, it might
        # have been uppercase, or had no hyphens.
        raise argparse.ArgumentTypeError(
            f"{comment}: '{uuid_string}' is a valid UUID but not in the required canonical lowercase "
            "hyphenated format (e.g., 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'). "
            f"Canonical form would be '{str(parsed_uuid)}'."
        )
    except ValueError:
        # The string is not a valid UUID structure at all.
        raise argparse.ArgumentTypeError(
            f"{comment}: '{uuid_string}' is not a valid UUID."
        )


def validate_json(path: str) -> str:
    """
    Validate path_str as json file. if not raise argparse.ArgumentTypeError
    """
    path_object = Path(path)
    if not path_object.is_file():
        raise argparse.ArgumentTypeError(f"File '{path}' is not a file.")
    try:
        json.loads(path_object.read_text(encoding="utf-8"))
    except json.JSONDecodeError as jde:
        raise argparse.ArgumentTypeError(f"File '{path}' is not a valid JSON file: {jde}")
    return path

def validate_xml(path: str) -> str:
    """
    Validate path_str as xml file. if not raise argparse.ArgumentTypeError
    """
    path_object = Path(path)
    if not path_object.is_file():
        raise argparse.ArgumentTypeError(f"File '{path}' is not a file.")
    try:
        ET.parse(path_object)
    except ET.ParseError as pe:
        raise argparse.ArgumentTypeError(f"File {path} is not a parsable XML: {pe}")
    except Exception as e:
        raise argparse.ArgumentTypeError(f"File '{path}' failed during parsing: {e}.")
    return path

def validate_yaml(path: str) -> str:
    """
    Validate path_str as yaml file. if not raise argparse.ArgumentTypeError
    """
    path_object = Path(path)
    if not path_object.is_file():
        raise argparse.ArgumentTypeError(f"File '{path}' is not a file.")

    try:
        yaml_filter.read_yaml(path)
    except Exception as e:
        raise argparse.ArgumentTypeError(f"File '{path}' failed during parsing: {e}")
    return path


def validate_txt(path: str) -> str:
    path_object = Path(path)
    if not path_object.is_file():
        raise argparse.ArgumentTypeError(f"File '{path}' is not a file.")
    if path_object.read_text(encoding="utf-8").strip() == "":
        raise argparse.ArgumentTypeError(f"File '{path}' is empty.")
    return path


def str_path_validator(path: str, comment: str = "", is_dir: bool = False, data_format: str|None = None) -> str:
    """
    Validate path_str as file. if not raise argparse.ArgumentTypeError

    Args:
        path: the string to test for being a file/directory
        comment: comment string for error message
        is_dir: check for being directory, otherwise file is assumed
        data_format: file data format
    Raises:
        argparse.ArgumentTypeError: when item isn't a file/directory

    Returns:
        str - on valid path
    """
    valid: bool = Path(path).is_dir() if is_dir else Path(path).is_file()
    if not valid:
        message: str = (
            f"For {comment}: {'Directory' if is_dir else 'File'} '{path}' not found."
        )
        raise argparse.ArgumentTypeError(message)
    if is_dir:
        return path
    if data_format is None:
        data_format = SUPPORTED_DATA_FORMATS[-1]
    if data_format == "json":
        path = validate_json(path)
    elif data_format == "xml":
        path = validate_xml(path)
    elif data_format == "yaml":
        path = validate_yaml(path)
    elif data_format == "txt":
        path = validate_txt(path)
    else:
        raise argparse.ArgumentTypeError(f"Unsupported data format: {data_format}")
    return path

def str_validator(item_str: str, comment: str = "String validation") -> str:
    """
    Validates if the given string is a non-empty string.
    """
    if not isinstance(item_str, str):
        raise argparse.ArgumentTypeError(f"{comment} Invalid type: String input must be a string, got {type(item_str)}.")
    return item_str

def get_cli_list_process(
    name: str,
    prompt_message: str,
    config: dict | None = None,
    cli_value=None,
):
    if config is None:
        config = {}
    is_mandatory = config.get("is_mandatory", False)
    is_confidential = config.get("is_confidential", False)
    validator_callback = config.get("validator_callback", None)
    validator_kws = config.get("validator_kws", {})
    arg_cli_name = f"--{name.replace('_', '-')}"
    if not cli_value or cli_value == [""]:  # Not provided via CLI, prompt the user
        while True:
            msg_items: list[str] = ["comma-separated"]
            prop = "mandatory" if is_mandatory else "optional"
            msg_items.append(prop)
            message: str = f"{prompt_message} ({'; '.join(msg_items)}): "
            input_method = getpass.getpass if is_confidential else input
            val_str = input_method(message).strip()
            if not val_str:
                if is_mandatory:
                    print(f"ERROR: {name} list is mandatory and requires at least one item.")
                    sys.exit(1)
                return []  # Optional and empty

            items = [item.strip() for item in val_str.split(",")]
            if is_mandatory and not items:  # Should be caught by 'not val_str' already
                print(f"ERROR: {name} list is mandatory and requires at least one item.")
                continue

            if not validator_callback:
                return items

            all_items_valid = True
            for item_path_str in items:
                if not item_path_str:  # Skip empty strings if user did "foo,,bar"
                    continue
                try:
                    item_path_str = validator_callback(
                        item_path_str, comment=prompt_message, **validator_kws
                    )
                except argparse.ArgumentTypeError as ae:
                    print(str(ae))
                    all_items_valid = False
                    break
            if not all_items_valid:
                continue  # Re-prompt for the whole list
            return items
    else:  # Provided via CLI (cli_value is a list, possibly empty if nargs='*')
        if is_mandatory and not cli_value:
            print(f"Error: {arg_cli_name} is mandatory and requires at least one item.")
            sys.exit(1)
        if not validator_callback:
            return cli_value
        for item_str in cli_value:
            try:
                item_str = validator_callback(
                    item_str, comment=prompt_message, **validator_kws
                )
            except argparse.ArgumentTypeError as ae:
                print(str(ae))
                sys.exit(1)
        return cli_value


def get_cli_string_process(
    name: str,
    prompt_message: str,
    config: dict | None = None,
    cli_value=None,
):
    if config is None:
        config = {}
    is_mandatory = config.get("is_mandatory", False)
    is_confidential = config.get("is_confidential", False)
    validator_callback = config.get("validator_callback", None)
    if not callable(validator_callback):
        validator_callback = str_validator

    validator_kws = config.get("validator_kws", {})
    arg_cli_name = f"--{name.replace('_', '-')}"
    input_method = getpass.getpass if is_confidential else input
    if cli_value is None:  # Not provided via CLI, prompt the user
        while True:
            msg_items: list[str] = []
            props = (
                ["mandatory"]
                if is_mandatory
                else ["optional", "press ENTER to use default"]
            )
            msg_items.extend(props)
            message: str = f"{prompt_message} ({'; '.join(msg_items)}): "
            val = input_method(message).strip()
            if not val:
                if is_mandatory:
                    print("Error: This field is mandatory.")
                    continue
                return ""  # Optional and empty
            if validator_callback:  # Only validate if non-empty value provided
                try:
                    val = validator_callback(
                        val, comment=prompt_message, **validator_kws
                    )
                except argparse.ArgumentTypeError as ae:
                    print(str(ae))
                    continue
            return val
    else:  # Provided via CLI
        if is_mandatory and not cli_value:  # e.g. user passed --splunk-url ""
            print(
                f"Error: {arg_cli_name} is mandatory and cannot be an empty string when provided explicitly."
            )
            sys.exit(1)

        if (
            cli_value and validator_callback
        ):  # Only validate if non-empty value provided
            try:
                cli_value = validator_callback(
                    cli_value, comment=prompt_message, **validator_kws
                )
            except argparse.ArgumentError as ae:
                print(ae.message)
                sys.exit(1)
        return cli_value


def get_cli_or_prompt(
    name: str,
    args: argparse.Namespace,
    prompt_message: str,
    config: dict | None = None,
) -> Any:
    """
    Retrieves a value from parsed command-line arguments or prompts the user if not provided.
    Includes logic for mandatory fields and basic validations.

    Args:
        name: The name of the attribute on the args object (e.g., 'splunk_url').
        args: The argparse Namespace object.
        prompt_message: The message to display to the user when prompting.
        config: configuration information, these are its attributes:
            is_mandatory: Boolean, True if the field must have a value.
            is_list: Boolean, True if the expected input is a list of strings.
            validator_callback: callback to validator of the argument with signature: name(item, comment)
            validator_kws: dict[str, str] | None = None,
    Returns:
        The retrieved or prompted value (string/list of strings/boolean).
        Exits script if CLI validation for mandatory/existing paths fails.
    """
    cli_value = getattr(args, name)
    # For error messages
    # arg_cli_name = f"--{name.replace('_', '-')}"
    if config is None:
        config = {}
    processor_method = get_cli_string_process
    if config.get("is_list", False):
        processor_method = get_cli_list_process
    return processor_method(
        name,
        prompt_message,
        config=config,
        cli_value=cli_value,
    )


def parse_cli_args(args: list[str] = sys.argv[1:]):
    parser = argparse.ArgumentParser(
        description="Generate data.yml for Jinja2 CLI, to be used with test_report_send.yml.j2 template.",
        # Shows default values in help
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Define command-line arguments
    # Mandatory
    parser.add_argument(
        "--splunk-url",
        default=None,
        help="Splunk HEC URL (for tests you can use: https://httpstat.us/403).",
    )
    parser.add_argument(
        "--splunk-token", default=None, help="Splunk HTTP Event Collector (HEC) token."
    )
    parser.add_argument(
        "--trs-ci-system",
        default=DEFAULTS["trs_ci_system"],
        help=f"CI System identifier. (SUPPORTED: ['{"', '".join(SUPPORTED_CI_NAMES)}'])",
    )
    parser.add_argument(
        "--reports-list",
        default=[],
        type=comma_separated_list,
        help="Comma-separated list of JUnit report XML files. Validation ensures file(s) exist",
    )

    # Optional
    parser.add_argument(
        "--splunk-channel",
        default=DEFAULTS["splunk_channel"],
        help="Splunk channel. (Optional)"
    )
    parser.add_argument("--splunk-index", default=None, help="Splunk index. (Optional)")
    parser.add_argument(
        "--trs-metadata-path",
        default=DEFAULTS["trs_metadata_path"],
        help="Path to a metadata file or directory. Validated if provided and non-empty. (Optional)",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULTS["output_dir"],
        help="Output directory for junit2json. (Optional - Jinja template has its own default if this is empty or not provided)",
    )

    # Boolean flags
    parser.add_argument(
        "--skip-ci-autodetect",
        action="store_true",
        help="If set, add 'trs_ci_system_autodetect: false' to the output. Default is to omit the key (implies true).",
    )
    parser.add_argument(
        "--skip-send",
        action="store_true",
        help="If set, add 'trs_do_send: false' to the output. Default is to omit the key (implies true).",
    )

    parser.add_argument(
        "--outfile",
        default=DEFAULTS["outfile"],
        help="Output YAML file name."
    )

    return parser.parse_args(args=args)


def build_context(args: argparse.Namespace) -> dict[str, str]:
    # 1. Dynamic variables (always calculated)
    context_data = {}
    context_data["playbook"] = tpl2pb(TEMPLATE_DEFAULT)
    local_now: datetime = datetime.now(timezone.utc).astimezone()
    context_data["current_date"] = local_now.strftime("%Y-%m-%d")
    context_data["current_time"] = local_now.strftime("%H:%M:%S %z%Z")
    try:
        context_data["username"] = getpass.getuser()
    except Exception:
        context_data["username"] = os.environ.get(
            "USER", os.environ.get("USERNAME", "unknown_user")
        )

    # 2. Process parameters (fetch from CLI or prompt, with validation)
    context_data["splunk_url"] = get_cli_or_prompt(
        "splunk_url",
        args,
        "Enter Splunk HEC URL",
        config={
            "is_mandatory": True,
            "validator_callback": str_url_validator,
        },
    )
    context_data["splunk_token"] = get_cli_or_prompt(
        "splunk_token",
        args,
        "Enter Splunk Token",
        config={
            "is_mandatory": True,
            "is_confidential": True,
            "validator_callback": str_uuid_validator,
        },
    )
    context_data["trs_ci_system"] = get_cli_or_prompt(
        "trs_ci_system",
        args,
        f"Enter CI System identifier (SUPPORTED: ['{"', '".join(SUPPORTED_CI_NAMES)}']).",
        config={
            "is_mandatory": True,
            "validator_callback": str_validator,
        },
    )

    context_data["reports_list"] = get_cli_or_prompt(
        "reports_list",
        args,
        "Enter JUnit files list",
        config={
            "is_mandatory": True,
            "is_list": True,
            "validator_callback": str_path_validator,
            "validator_kws": {
                "data_format": "xml",
            }
        },
    )

    context_data["splunk_channel"] = get_cli_or_prompt(
        "splunk_channel", args, "Enter Splunk Channel"
    )

    context_data["splunk_index"] = get_cli_or_prompt(
        "splunk_index", args, "Enter Splunk Index"
    )

    context_data["trs_metadata_path"] = get_cli_or_prompt(
        "trs_metadata_path",
        args,
        "Enter path to metadata file/directory",
        config={
            "validator_callback": str_path_validator,  # Validated only if a non-empty path is provided
            "validator_kws": {
                "data_format": "json",
            },
        },
    )

    context_data["outfile"] = get_cli_or_prompt(
        "outfile",
        args,
        "Enter outfile name",
    )
    context_data["output_dir"] = get_cli_or_prompt(
        "output_dir",
        args,
        "Enter output directory",
        config={
            "validator_callback": str_path_validator,
            "validator_kws": {"is_dir": True},
        },
    )

    # 3. Conditionally add boolean flag-derived variables
    if args.skip_ci_autodetect:
        context_data["trs_ci_system_autodetect"] = False
    if args.skip_send:
        context_data["trs_do_send"] = False

    return context_data



def main():
    args = parse_cli_args(args=sys.argv[1:])
    context_data = build_context(args)

    # 4. Write to YAML file
    try:
        outfile = os.path.join(context_data["output_dir"], context_data["outfile"])
        output_file = Path(outfile)
        if output_file.exists():
            print(f"ERROR: File {output_file} already exists. Please delete it or use a different name.")
            return 3
        # Ensure parent directory exists if --outfile is like "some/dir/data.yml"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        yaml_filter.write_yaml(context_data, outfile, config=RUAMEL_CONFIG, width=YAML_LINE_WIDTH)

    except KeyError as ke:
        print(f"Missing key in context_data '{context_data}': {ke}", file=sys.stderr)
        return 1
    except PermissionError as pe:
        print(f"Error writing YAML file: {pe}", file=sys.stderr)
        return 1
    print(f"Successfully generated {context_data['outfile']}\n")
    print("You can now use this with Jinja2 CLI, for example:")
    prefix = "    "
    cmd_items = ["jinja"]
    cmd_items += [
        "--format=yaml",
        f'--data="{outfile}"',
        f'--output="{context_data["output_dir"]}/{context_data["playbook"]}"',
        f'"{TEMPLATE_DEFAULT}"',
    ]
    cmd_items_len: int = len(cmd_items)
    for idx, item in enumerate(cmd_items):
        curr_prefix = prefix if idx == 0 else prefix * 2
        suffix = " \\" if idx != (cmd_items_len - 1) else ""
        print(f"{curr_prefix}{item}{suffix}", end="\n")

    return 0


if __name__ == "__main__":
    # Ensure PyYAML is installed
    sys.exit(main())
