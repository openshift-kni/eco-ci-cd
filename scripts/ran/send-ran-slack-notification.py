#! /usr/bin/env python3
"""Send RAN test report notification to Slack.

Usage:
    python send-ran-report-notification.py \
        --webhook-url <slack_webhook_url> \
        --build <build_version> \
        --polarion-url <polarion_url> \
        --job-url <prow_job_url> \
        --reportportal-url-3node <url> \
        --reportportal-url-standard <url>
"""

import os
import sys
import logging
import argparse
import subprocess

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)


def construct_message(args):
    """Construct the Slack message for RAN report notification."""
    sections = []

    # Header
    sections.append(f"📊 *Build: {args.build}*")

    # 3-Node MNO section
    if args.reportportal_url_3node:
        section = "\n*3-Node MNO*\n___________"
        section += f"\nSent to Report Portal: {args.reportportal_url_3node}"
        section += f"\nSent to Polarion: {args.polarion_url}"
        sections.append(section)

    # Standard MNO section
    if args.reportportal_url_standard:
        section = "\n*Standard MNO*\n____________"
        section += f"\nSent to Report Portal: {args.reportportal_url_standard}"
        section += f"\nSent to Polarion: {args.polarion_url}"
        sections.append(section)

    # Footer with Prow job URL
    if args.job_url:
        sections.append(f"\nProw Job: {args.job_url}")

    return "\n".join(sections)


def send_to_slack(webhook_url, message):
    """Send message to Slack using send-slack-notification.py script."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    scripts_dir = os.path.dirname(script_dir)
    notification_script = os.path.join(scripts_dir, "slack-notification", "send-slack-notification.py")

    cmd = [
        sys.executable,
        notification_script,
        "--webhook-url", webhook_url,
        "--custom-message", message
    ]

    try:
        logging.info("Sending notification to Slack...")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stdout:
            logging.info(result.stdout)
        logging.info("Message sent to Slack successfully!")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to send message: {e}")
        if e.stderr:
            logging.error(e.stderr)
        return False
    except FileNotFoundError:
        logging.error(f"Could not find script: {notification_script}")
        return False


def parse_arguments():
    parser = argparse.ArgumentParser(description="Send RAN test report notification to Slack")
    parser.add_argument("--webhook-url", required=True, help="Slack webhook URL")
    parser.add_argument("--build", required=True, help="OCP build version")
    parser.add_argument("--polarion-url", required=True, help="Polarion test run URL")
    parser.add_argument("--job-url", required=True, help="Prow job URL for 'more info' link")
    parser.add_argument("--reportportal-url-3node", required=True, help="Report Portal URL for 3-node")
    parser.add_argument("--reportportal-url-standard", required=True, help="Report Portal URL for standard")
    return parser.parse_args()


def main():
    args = parse_arguments()
    message = construct_message(args)

    logging.info(f"Constructed message:\n{message}")

    if not send_to_slack(args.webhook_url, message):
        sys.exit(1)


if __name__ == "__main__":
    main()
