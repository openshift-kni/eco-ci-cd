#! /usr/bin/env python3

import requests
import sys
import logging
import argparse
import jinja2


def construct_message(args: argparse.Namespace):
    """Construct the message to send to Slack"""

    tagged_users = " ".join([f"<@{user}>" for user in args.users])

    environment = jinja2.Environment(loader=jinja2.BaseLoader)
    template = environment.from_string("""

Failed Job:
{% if args.version %}
    Release: {{args.version}} {% endif -%}
{% if args.job_name %}
    Job: {{args.job_name}} {% endif -%}
{% if args.link %}
    <{{args.link}}|Link to failed job> {% endif %}

{{ tagged_users }}

""")
    return template.render(args=args, tagged_users=tagged_users)


def log_config(debug: bool):
    log_level = 'DEBUG' if debug else 'INFO'
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )

    logging.debug(f"Logger started with debug mode: {log_level}")


def send_to_slack(args: argparse.Namespace):
    """Send release info to Slack channel"""

    headers = {
        "Content-Type": "application/json"
    }
    if args.custom_message:
        logging.info("Sending custom message to Slack")
        slack_message = args.custom_message
    else:
        logging.info("Constructing message to send to Slack")
        slack_message = construct_message(args)

    logging.debug(f"Sending message to Slack: {slack_message}")

    if args.dry_run:
        logging.info(f"Dry run mode")
        print(slack_message)
    else:
        response = requests.post(url=args.webhook_url, headers=headers, json={"text": slack_message})
        response.raise_for_status()
        logging.debug(f"Response from Slack: {response.text}")
        logging.info("Message sent to Slack")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Send release information to Slack"
    )
    # Required arguments
    parser.add_argument(
        "--webhook-url", required=True, help="Slack webhook URL"
    )
    parser.add_argument(
        "--version", required=False, help="Release version"
    )
    parser.add_argument(
        "--job-name", required=False, help="Name of the job"
    )
    # Direct values
    parser.add_argument(
        "--link", default="", required=False, help="Link to failed job"
    )
    parser.add_argument(
        "--users", nargs='+', required=False,
        help="Users to tag in Slack"
    )
    parser.add_argument(
        "--custom-message", required=False,
        help="Custom message to send in Slack"
    )
    parser.add_argument(
        "--debug", action="store_true", required=False,
        help="Enable debug mode"
    )
    parser.add_argument(
        "--dry-run", action="store_true", required=False, default=False,
        help="Dry run mode, only print the message to the console"
    )
    return parser.parse_args()


def main():
    args = parse_arguments()
    log_config(args.debug)
    send_to_slack(args)


if __name__ == "__main__":
    main()
