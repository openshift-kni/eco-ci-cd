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

def construct_message(release_info, prow_job_url, phase1_prow_url=None):
    """Construct the Slack message content
    
    Args:
        release_info (dict): Release information dictionary
        prow_job_url (str): Current/main Prow job URL
        phase1_prow_url (str, optional): Phase 1 Prow job URL if available
    
    Returns:
        str: Formatted message to send to Slack
    """
    
    # Determine job labels based on whether this is a multi-phase workflow
    has_phase1 = bool(phase1_prow_url)
    main_job_label = "Phase 2 Job" if has_phase1 else "Prow Job"
    
    # Build links dynamically to avoid duplication
    links = [
        f"Jira: {release_info['jira_card_link']}",
        f"Polarion: {release_info['polarion_url']}"
    ]
    
    # Add job links in logical order (Phase 1 first if exists, then main job)
    if has_phase1:
        links.append(f"Phase 1 Job: <{phase1_prow_url}|View Phase 1 Job>")
    
    links.append(f"{main_job_label}: <{prow_job_url}|View {main_job_label}>")
    
    # Construct the final links section
    links_section = "Links:\n" + "\n".join(f"- {link}" for link in links)
    
    message = f"""🚀 *Release {release_info['version']}*

{links_section}

*Environment:*
• *Cluster:* {release_info['test_env']['cluster_name']}
• *NIC:* {release_info['test_env']['nic']}
• *Secondary NIC:* {release_info['test_env']['secondary_nic']}
• *CNF Image:* `{release_info['test_env']['cnf_image_version']}`
• *DPDK Image:* `{release_info['test_env']['dpdk_image_version']}`
"""
    
    return message


def send_to_slack(webhook_url, message):
    """Send message to Slack by calling the send-slack-notification.py script
    
    Args:
        webhook_url (str): Slack webhook URL
        message (str): Formatted message to send
    
    Returns:
        bool: True if successful, False otherwise
    """
    
    # Get the path to the send-slack-notification.py script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up one level: scripts/network/ -> scripts/
    scripts_dir = os.path.dirname(script_dir)
    notification_script = os.path.join(scripts_dir, "slack-notification", "send-slack-notification.py")
    
    # Build the command to call the notification script
    cmd = [
        sys.executable,  # Use the same Python interpreter
        notification_script,
        "--webhook-url", webhook_url,
        "--custom-message", message
    ]
    
    try:
        logging.info("Calling send-slack-notification.py script...")
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )
        
        # Log output from the notification script
        if result.stdout:
            logging.info(f"Script output: {result.stdout}")
        
        logging.info("✅ Message sent to Slack successfully!")
        return True
        
    except subprocess.CalledProcessError as e:
        logging.error(f"❌ Failed to send message to Slack: {e}")
        if e.stderr:
            logging.error(f"Error output: {e.stderr}")
        return False
    except FileNotFoundError:
        logging.error(f"❌ Could not find notification script at: {notification_script}")
        return False

def parse_arguments():
    parser = argparse.ArgumentParser(description="Send release information to Slack")
    
    # Required arguments
    parser.add_argument("--webhook-url", required=True, help="Slack webhook URL")
    parser.add_argument("--version", required=True, help="Release version")
    
    # Optional arguments with defaults
    parser.add_argument("--registry-url", default="https://registry.stage.redhat.io/openshift4", 
                       help="Registry URL for images (default: %(default)s)")    
    # Direct values
    parser.add_argument("--jira-link", default="", help="Jira card link")
    parser.add_argument("--polarion-url", default="", help="Polarion URL")
    parser.add_argument("--cluster-name", default="", help="Cluster name")
    parser.add_argument("--nic", default="", help="NIC name")
    parser.add_argument("--secondary-nic", default="", help="Secondary NIC name")
    parser.add_argument("--phase1-build-id", default="", help="Phase 1 build ID")
    
    return parser.parse_args()

def parse_version(version_string):
    """Parse version string and return major, minor components and determine RHEL version."""
    try:
        major, minor = int(version_string.split('.')[0]), int(version_string.split('.')[1])
        rhel_version = "rhel8" if (major, minor) <= (4, 15) else "rhel9"
        logging.info(f"Detected version {version_string}, using '{rhel_version}' images.")
        return major, minor, rhel_version
    except (ValueError, IndexError):
        logging.error(f"❌ Error: Invalid version format: '{version_string}'. Expected 'major.minor.patch'.")
        sys.exit(1)

def construct_job_name(major, minor):
    """Construct the appropriate job name based on version."""
    if (major, minor) > (4, 17):
        return f"periodic-ci-openshift-kni-eco-ci-cd-main-cnf-network-phase2-{major}.{minor}-cnf-network-functional-tests"
    else:
        return f"periodic-ci-openshift-kni-eco-ci-cd-main-cnf-network-{major}.{minor}-cnf-network-functional-tests"

def construct_prow_urls(major, minor, phase1_build_id=None):
    """Construct Prow job URLs for current and optionally phase1/phase2 jobs.
    
    Args:
        major (int): Major version number
        minor (int): Minor version number  
        phase1_build_id (str, optional): Phase 1 build ID. If None or empty, 
                                        phase1 URL will not be generated.
    
    Returns:
        tuple: (current_prow_url, phase1_prow_url or None)
    """
    prow_base_url = "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/"
    
    # Current job URL
    job_name = construct_job_name(major, minor)
    cnf_network_link = f"{prow_base_url}{job_name}/"

    # BUILD_ID is automatically being passed from the prow job
    build_id = os.environ.get("BUILD_ID")
    
    current_prow_url = f"{cnf_network_link}{build_id}" if build_id else "Job URL Not Available"
    
    # Phase 1 job URL (only if phase1_build_id is provided and not empty)
    phase1_prow_url = None
    if phase1_build_id and phase1_build_id.strip():
        phase1_job_name = f"periodic-ci-openshift-kni-eco-ci-cd-main-cnf-network-phase1-{major}.{minor}-cnf-network-functional-tests"
        phase1_cnf_network_link = f"{prow_base_url}{phase1_job_name}/"
        phase1_prow_url = f"{phase1_cnf_network_link}{phase1_build_id.strip()}"
        logging.info(f"Phase 1 Prow URL constructed: {phase1_prow_url}")
    else:
        logging.debug("Phase 1 build ID not provided or empty - skipping Phase 1 URL generation")
    
    return current_prow_url, phase1_prow_url

def create_release_info(args, rhel_version):
    """Create the release info dictionary."""
    return {
        "version": args.version,
        "jira_card_link": args.jira_link,
        "polarion_url": args.polarion_url,
        "test_env": {
            "cluster_name": args.cluster_name,
            "nic": args.nic,
            "secondary_nic": args.secondary_nic,
            "cnf_image_version": f"{args.registry_url}/cnf-{rhel_version}:v{args.version}",
            "dpdk_image_version": f"{args.registry_url}/dpdk-base-{rhel_version}:v{args.version}"
        }
    }

def main():
    """Main function to orchestrate the Slack notification process."""
    args = parse_arguments()
    
    # Parse version and determine RHEL version
    major, minor, rhel_version = parse_version(args.version)
    
    # Construct Prow job URLs
    current_prow_url, phase1_prow_url = construct_prow_urls(major, minor, args.phase1_build_id)
    
    # Construct the relevant information for the slack message
    release_info = create_release_info(args, rhel_version)
    
    # Construct the message
    message = construct_message(release_info, current_prow_url, phase1_prow_url)
    
    # Log the workflow type for debugging
    workflow_type = "multi-phase" if phase1_prow_url else "single-phase"
    logging.info(f"Constructed message for {workflow_type} workflow")
    
    # Send notification to Slack via the notification script
    message_sent = send_to_slack(args.webhook_url, message)
    
    if not message_sent:
        logging.error("❌ Error: Slack notification failed.")
        sys.exit(1)
    
    logging.info("✅ Slack notification process completed successfully!")

if __name__ == "__main__":
    main()
