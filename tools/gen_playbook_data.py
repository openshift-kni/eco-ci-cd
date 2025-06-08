#!/usr/bin/env python3
"""
Generates playbook extra data file
"""
import argparse
from operator import methodcaller
import socket
from typing import Any, Callable
import urllib.parse
import uuid
from datetime import datetime, timezone
import getpass
import os
import sys
from pathlib import Path
try:
    import yaml
except ImportError:
    print(
        "PyYAML library is not installed. Please install it with 'pip install PyYAML'",
        file=sys.stderr,
    )
    sys.exit(1)

SUPPORTED_CI_NAMES = [
    "dci",
    "jenkins",
    "prow"
]
TPL_DEFAULT = "templates/test_report_send.yml.j2"

# Custom representer for booleans to ensure lowercase 'true'/'false'
def represent_bool_lowercase(dumper, data):
    if data:
        return dumper.represent_scalar('tag:yaml.org,2002:bool', 'true')
    else:
        return dumper.represent_scalar('tag:yaml.org,2002:bool', 'false')
# Add this representer to the Dumper you are using (e.g., SafeDumper)
# PyYAML's default dumper is often SafeDumper, but it's good to be explicit.
yaml.add_representer(bool, represent_bool_lowercase, Dumper=yaml.SafeDumper)
# Also for the base Dumper if used
yaml.add_representer(bool, represent_bool_lowercase, Dumper=yaml.Dumper)

def comma_separated_list(arg) -> list[str]:
    return arg.split(',')


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
        raise argparse.ArgumentTypeError(f"{comment} - must be a string, got {type(item_url_str)}.")

    # 2. Parse the URL
    # urlparse is generally lenient and rarely raises errors for string inputs,
    # so we check its components.
    try:
        parsed_url = urllib.parse.urlparse(item_url_str)
    except Exception as e:
        # Catch any unexpected error during parsing, though unlikely for urlparse with strings.
        raise argparse.ArgumentTypeError(f"{comment} Could not be parsed as URL '{item_url_str}': {e}")

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


def str_uuid_validator(item: str, comment: str = "") -> str:
    """
    Validate str as UUID if not, raise argparse.ArgumentTypeError

    Args:
        item: str - the string to test
        comment: str - comment for error

    Raises:
        argparse.ArgumentTypeError when the item isn't a UUID

    Returns:
        str - the valid UUID item
    """


def str_uuid_validator(uuid_string: str, comment: str = "") -> str:
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
        raise argparse.ArgumentTypeError(f"{comment} Invalid type: UUID input must be a string, got {type(uuid_string)}.")

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
        else:
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


def str_path_validator(path: str, comment: str = "", is_dir: bool = False) -> str:
    """
    Validate path_str as file. if not raise argparse.ArgumentTypeError

    Args:
        path: the string to test for being a file/directory
        comment: comment string for error message
        is_dir: check for being directory, otherwise file is assumed
    Raises:
        argparse.ArgumentTypeError: when item isn't a file/directory

    Returns:
        str - on valid path
    """
    valid: bool = Path(path).is_dir() if is_dir else Path(path).is_file()
    if not valid:
        message: str = f"For {comment}: {"Directory" if is_dir else "File"} '{path}' not found."
        raise argparse.ArgumentTypeError(message)
    return path


def get_cli_or_prompt(
    args: argparse.Namespace,
    arg_name_on_args_obj: str,
    prompt_message: str,
    is_mandatory: bool = False,
    is_list: bool = False,
    validator_callback: Callable[[], None] = None,
    validator_kws: dict[str, str] = {}
) -> Any:
    """
    Retrieves a value from parsed command-line arguments or prompts the user if not provided.
    Includes logic for mandatory fields and basic validations.

    Args:
        args: The argparse Namespace object.
        arg_name_on_args_obj: The name of the attribute on the args object (e.g., 'splunk_url').
        prompt_message: The message to display to the user when prompting.
        is_mandatory: Boolean, True if the field must have a value.
        is_list: Boolean, True if the expected input is a list of strings.
        validator_callback: callback to validator of the argument with signature: name(item, comment)
    Returns:
        The retrieved or prompted value (string/list of strings/boolean).
        Exits script if CLI validation for mandatory/existing paths fails.
    """
    cli_value = getattr(args, arg_name_on_args_obj)
    # For error messages
    arg_cli_name = f"--{arg_name_on_args_obj.replace('_', '-')}"

    if is_list:
        if cli_value is None:  # Not provided via CLI, prompt the user
            while True:
                msg_items: list[str] = ["comma-separated"]
                if is_mandatory:
                    msg_items.append("mandatory")
                else:
                    msg_items.append("optional")
                message: str = f"{prompt_message} ({'; '.join(msg_items)}): "
                val_str = input(prompt=message).strip()
                if not val_str:
                    if is_mandatory:
                        print(f"{arg_name_on_args_obj} list is mandatory and requires at least one item.")
                        sys.exit(1)
                    return []  # Optional and empty

                items = [item.strip() for item in val_str.split(",")]
                if (is_mandatory and not items):  # Should be caught by 'not val_str' already
                    print("Error: This list is mandatory and requires at least one item.")
                    continue

                if not validator_callback:
                    return items

                all_items_valid = True
                for item_path_str in items:
                    if (not item_path_str):  # Skip empty strings if user did "foo,,bar"
                        continue
                    try:
                        item_path_str = validator_callback(
                            item_path_str,
                            comment=prompt_message,
                            **validator_kws
                        )
                    except argparse.ArgumentError as ae:
                        print(ae.message)
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
            for item_path_str in cli_value:
                try:
                    item_path_str = validator_callback(
                        item_path_str,
                        comment=prompt_message,
                        **validator_kws
                    )
                except argparse.ArgumentError as ae:
                    print(ae.message)
                    sys.exit(1)
            return cli_value

    else:  # String value
        if cli_value is None:  # Not provided via CLI, prompt the user
            while True:
                msg_items: list[str] = []
                if is_mandatory:
                    msg_items.append("mandatory")
                else:
                    msg_items.append("optional")
                    msg_items.append("press ENTER to use default")
                message: str = f"{prompt_message} ({'; '.join(msg_items)}): "
                val = input(prompt=message).strip()
                if not val:
                    if is_mandatory:
                        print("Error: This field is mandatory.")
                        continue
                    return ""  # Optional and empty
                if validator_callback:  # Only validate if non-empty value provided
                    try:
                        val = validator_callback(val, comment=prompt_message, **validator_kws)
                    except argparse.ArgumentError as ae:
                        print(ae.message)
                        continue
                return val
        else:  # Provided via CLI
            if is_mandatory and not cli_value:  # e.g. user passed --splunk-url ""
                print(f"Error: {arg_cli_name} is mandatory and cannot be an empty string when provided explicitly.")
                sys.exit(1)

            if (cli_value and validator_callback):  # Only validate if non-empty value provided
                try:
                    cli_value = validator_callback(cli_value, comment=prompt_message, **validator_kws)
                except argparse.ArgumentError as ae:
                    print(ae.message)
                    sys.exit(1)
            return cli_value


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
        help="Splunk URL (e.g., https://splunk.example.com:8088).",
    )
    parser.add_argument(
        "--splunk-token",
        default=None,
        help="Splunk HTTP Event Collector (HEC) token."
    )
    parser.add_argument(
        "--trs-ci-system",
        default=None,
        help=f"CI System identifier. (SUPPORTED: ['{"', '".join(SUPPORTED_CI_NAMES)}'])",
    )
    parser.add_argument(
        "--reports-list",
        default="",
        type=comma_separated_list,
        help="Comma-separated list of JUnit report XML files. Validation ensures file(s) exist",
    )

    # Optional
    parser.add_argument(
        "--splunk-channel",
        default=None,
        help="Splunk channel. (Optional)"
    )
    parser.add_argument(
        "--splunk-index",
        default=None,
        help="Splunk index. (Optional)"
    )
    parser.add_argument(
        "--trs-metadata-path",
        default=None,
        help="Path to a metadata file or directory. Validated if provided and non-empty. (Optional)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory for junit2json. (Optional - Jinja template has its own default if this is empty or not provided)",
    )

    # Boolean flags
    parser.add_argument(
        '--skip-ci-detect',
        action='store_true',
        help="If set, add 'trs_ci_detect_skip: true' to the output. Default is to omit the key (implies false)."
    )
    parser.add_argument(
        '--skip-send',
        action='store_true',
        help="If set, add 'trs_do_send: false' to the output. Default is to omit the key (implies true)."
    )

    parser.add_argument(
        "--outfile",
        default="data.yml",
        help="Output YAML file name."
    )

    return parser.parse_args(args=args)


def build_context(args: argparse.Namespace) -> dict[str,str]:
    # 1. Dynamic variables (always calculated)
    context_data = {}
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
        args,
        "splunk_url",
        "Enter Splunk HEC URL",
        is_mandatory=True,
        validator_callback=str_url_validator
    )
    context_data["splunk_token"] = get_cli_or_prompt(
        args,
        "splunk_token",
        "Enter Splunk Token",
        is_mandatory=True,
        validator_callback=str_uuid_validator
    )
    context_data["trs_ci_system"] = get_cli_or_prompt(
        args,
        "trs_ci_system",
        f"Enter CI System identifier (SUPPORTED: ['{"', '".join(SUPPORTED_CI_NAMES)}']).",
        is_mandatory=True
    )

    context_data["reports_list"] = get_cli_or_prompt(
        args,
        "reports_list",
        "Enter JUnit files list",
        is_mandatory=True,
        is_list=True,
        validator_callback=str_path_validator
    )

    context_data["splunk_channel"] = get_cli_or_prompt(
        args,
        "splunk_channel",
        "Enter Splunk Channel"
    )

    context_data["splunk_index"] = get_cli_or_prompt(
        args,
        "splunk_index",
        "Enter Splunk Index"
    )

    context_data["trs_metadata_path"] = get_cli_or_prompt(
        args,
        "trs_metadata_path",
        "Enter path to metadata file/directory",
        validator_callback=str_path_validator,  # Validated only if a non-empty path is provided
    )

    context_data["output_dir"] = get_cli_or_prompt(
        args,
        "output_dir",
        "Enter output directory",
        str_path_validator,
        validator_kws={"is_dir": True}
    )

    # 3. Conditionally add boolean flag-derived variables
    if args.skip_ci_detect:
        context_data['trs_ci_detect_skip'] = True
    if args.skip_send:
        context_data['trs_do_send'] = False

    return context_data

def main():
    args = parse_cli_args(args=sys.argv[1:])
    context_data = build_context(args)

    # 4. Write to YAML file
    try:
        output_file_path = Path(args.outfile)
        # Ensure parent directory exists if --outfile is like "some/dir/data.yml"
        output_file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file_path, "w") as f:
            yaml.dump(
                context_data,
                f,
                sort_keys=True,
                default_flow_style=False,
                indent=2,
                explicit_start=True
            )
        print(f"Successfully generated {args.outfile}\n")
        print("You can now use this with Jinja2 CLI, for example:")
        prefix = "    "
        cmd_items = [f"jinja"]
        cmd_items += [
            f"--format=yaml",
            f"--data=\"{output_file_path}\"",
            f"--output=\"{os.path.basename(TPL_DEFAULT).replace('.j2','')}\"",
            f"\"{TPL_DEFAULT}\"",
        ]
        cmd_items_len: int = len(cmd_items)
        for idx, item in enumerate(cmd_items):
            print(prefix, end="")
            if idx != 0:
                print(prefix, end="")
            print(item, end="")
            if idx != (cmd_items_len - 1):
                print(" \\", end="")
            print("", end="\n")

    except Exception as e:
        print(f"Error writing YAML file '{
              args.outfile}': {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    # Ensure PyYAML is installed
    sys.exit(main())
