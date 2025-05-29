#!/usr/bin/env python3

import argparse
import yaml
from datetime import datetime
import getpass
import os
import sys
from pathlib import Path

SUPPORTED_CI_NAMES = [
    "dci",
    "jenkins",
    "prow"
]

def get_cli_or_prompt(
    args,
    arg_name_on_args_obj,
    prompt_message,
    is_mandatory=False,
    is_list=False,
    validate_as_existing_path=False,
    validate_items_as_existing_files=False,
):
    """
    Retrieves a value from parsed command-line arguments or prompts the user if not provided.
    Includes logic for mandatory fields and basic validations.

    Args:
        args: The argparse Namespace object.
        arg_name_on_args_obj: The name of the attribute on the args object (e.g., 'splunk_url').
        prompt_message: The message to display to the user when prompting.
        is_mandatory: Boolean, True if the field must have a value.
        is_list: Boolean, True if the expected input is a list of strings.
        validate_as_existing_path: Boolean, True to validate if a non-empty string path exists.
        validate_items_as_existing_files: Boolean, True to validate if all items in a list are existing files.

    Returns:
        The retrieved or prompted value (string or list of strings).
        Exits script if CLI validation for mandatory/existing paths fails.
    """
    cli_value = getattr(args, arg_name_on_args_obj)
    # For error messages
    arg_cli_name = f"--{arg_name_on_args_obj.replace('_', '-')}"

    if is_list:
        if cli_value is None:  # Not provided via CLI, prompt the user
            while True:
                val_str = input(
                    f"{prompt_message} (comma-separated; optional: press Enter to skip): "
                ).strip()
                if not val_str:
                    if is_mandatory:
                        print(
                            "Error: This list is mandatory and requires at least one item."
                        )
                        continue
                    return []  # Optional and empty

                items = [item.strip() for item in val_str.split(",")]
                if (
                    is_mandatory and not items
                ):  # Should be caught by 'not val_str' already
                    print(
                        "Error: This list is mandatory and requires at least one item."
                    )
                    continue

                if validate_items_as_existing_files:
                    all_items_valid = True
                    for item_path_str in items:
                        if (
                            not item_path_str
                        ):  # Skip empty strings if user did "foo,,bar"
                            continue
                        if not Path(item_path_str).is_file():
                            print(
                                f"Error: File '{item_path_str}' for '{
                                    prompt_message
                                }' not found."
                            )
                            all_items_valid = False
                            break
                    if not all_items_valid:
                        continue  # Re-prompt for the whole list
                return items
        else:  # Provided via CLI (cli_value is a list, possibly empty if nargs='*')
            if is_mandatory and not cli_value:
                print(
                    f"Error: {
                        arg_cli_name
                    } is mandatory and requires at least one item."
                )
                sys.exit(1)
            if validate_items_as_existing_files:
                for item_path_str in cli_value:
                    if not Path(item_path_str).is_file():
                        print(
                            f"Error: File '{item_path_str}' provided via {
                                arg_cli_name
                            } not found."
                        )
                        sys.exit(1)
            return cli_value

    else:  # String value
        if cli_value is None:  # Not provided via CLI, prompt the user
            while True:
                val = input(f"{prompt_message}: ").strip()
                if not val:
                    if is_mandatory:
                        print("Error: This field is mandatory.")
                        continue
                    return ""  # Optional and empty

                if (
                    validate_as_existing_path
                ):  # Only validate if non-empty value provided
                    if not Path(val).exists():
                        print(
                            f"Error: Path '{val}' for '{
                                prompt_message
                            }' does not exist."
                        )
                        continue
                return val
        else:  # Provided via CLI
            if is_mandatory and not cli_value:  # e.g. user passed --splunk-url ""
                print(
                    f"Error: {
                        arg_cli_name
                    } is mandatory and cannot be an empty string when provided explicitly."
                )
                sys.exit(1)
            if (
                cli_value and validate_as_existing_path
            ):  # Only validate if non-empty value provided
                if not Path(cli_value).exists():
                    print(
                        f"Error: Path '{cli_value}' provided via {
                            arg_cli_name
                        } does not exist."
                    )
                    sys.exit(1)
            return cli_value


def main():
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
        "--splunk-token", default=None, help="Splunk HTTP Event Collector (HEC) token."
    )
    parser.add_argument(
        "--trs-ci-system",
        default=None,
        help=f"CI System identifier. (SUPPORTED: ['{"', '".join(SUPPORTED_CI_NAMES)}']).",
    )
    parser.add_argument(
        "--reports-list",
        nargs="*",
        default=None,
        help="Space-separated list of JUnit report XML files. Validation ensures file(s) exist",
    )

    # Optional
    parser.add_argument(
        "--splunk-channel", default=None, help="Splunk channel. (Optional)"
    )
    parser.add_argument("--splunk-index", default=None,
                        help="Splunk index. (Optional)")
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

    parser.add_argument("--outfile", default="data.yml",
                        help="Output YAML file name.")

    args = parser.parse_args()
    context_data = {}

    # 1. Dynamic variables (always calculated)
    context_data["current_date"] = datetime.now().strftime("%Y-%m-%d")
    context_data["current_time"] = datetime.now().strftime("%H:%M:%S")
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
        is_mandatory=True
    )
    context_data["splunk_token"] = get_cli_or_prompt(
        args,
        "splunk_token",
        "Enter Splunk Token",
        is_mandatory=True
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
        "Enter JUnit report files",
        is_mandatory=True,
        is_list=True,
        validate_items_as_existing_files=True,
    )

    context_data["splunk_channel"] = get_cli_or_prompt(
        args,
        "splunk_channel",
        "Enter Splunk Channel (optional, press Enter to skip)"
    )
    context_data["splunk_index"] = get_cli_or_prompt(
        args,
        "splunk_index",
        "Enter Splunk Index (optional, press Enter to skip)"
    )


    context_data["trs_metadata_path"] = get_cli_or_prompt(
        args,
        "trs_metadata_path",
        "Enter path to metadata file/directory (optional, press Enter to skip)",
        validate_as_existing_path=True,  # Validated only if a non-empty path is provided
    )

    context_data["output_dir"] = get_cli_or_prompt(
        args,
        "output_dir",
        "Enter output directory (optional, press Enter for Jinja default)",
    )

    # 3. Write to YAML file
    try:
        output_file_path = Path(args.outfile)
        # Ensure parent directory exists if --outfile is like "some/dir/data.yml"
        output_file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file_path, "w") as f:
            yaml.dump(
                context_data, f, sort_keys=False, default_flow_style=False, indent=2
            )
        print(f"Successfully generated {args.outfile}")
        print("\nYou can now use this with Jinja2 CLI, for example:")
        print(f"  jinja2 test_report_send.yml.j2 {
              args.outfile} -o output_playbook.yml")
    except Exception as e:
        print(f"Error writing YAML file '{
              args.outfile}': {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    # Ensure PyYAML is installed
    try:
        import yaml
    except ImportError:
        print(
            "PyYAML library is not installed. Please install it with 'pip install PyYAML'",
            file=sys.stderr,
        )
        sys.exit(1)
    main()
