import requests
import os
import sys
import logging
import argparse

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

def send_to_slack(webhook_url, release_info, prow_job_url):
    """Send release info to Slack channel"""
    
    message = f"""🚀 **Release {release_info['version']}**

Links:
- Jira: {release_info['jira_card_link']}
- Polarion: {release_info['polarion_url']}
- Prow Job: <{prow_job_url}|View Prow Job>

Environment:
- Cluster: {release_info['test_env']['cluster_name']}
- NIC: {release_info['test_env']['nic']}
- SECONDARY_NIC: {release_info['test_env']['secondary_nic']}
- CNF Image: {release_info['test_env']['cnf_image_version']}
- DPDK Image: {release_info['test_env']['dpdk_image_version']}
"""

    payload = {"text": message}
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=30)
        response.raise_for_status()
        logging.info("✅ Message sent to Slack!")
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Failed to send message to Slack: {e}")
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
    
    return parser.parse_args()
    
def main():
    args = parse_arguments()
    
    # Determine RHEL version based on the cluster version
    rhel_version = "rhel9"  # Default to rhel9
    try:
        # Compare version as a tuple of integers, e.g., (4, 14) <= (4, 15)
        major, minor, *_ = map(int, args.version.split('.'))
        if (major, minor) <= (4, 15):
            rhel_version = "rhel8"
        logging.info(f"Detected version {args.version}, using '{rhel_version}' images.")
    except (ValueError, IndexError):
        logging.error(f"❌ Error: Invalid version format: '{args.version}'. Expected 'major.minor.patch'.")
        sys.exit(1)  

    # Construct Prow job base URL
    prow_base_url = "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/"
    job_name = f"periodic-ci-openshift-kni-eco-ci-cd-main-cnf-network-{major}.{minor}-cnf-network-functional-tests"
    cnf_network_link = f"{prow_base_url}{job_name}/"
    build_id = os.environ.get("BUILD_ID")

    # Construct the Prow job URL
    if build_id:
        prow_job_url = f"{cnf_network_link}{build_id}"
    else:
        prow_job_url = "Job URL Not Available"
        
    release_info = {
        "version": args.version,
        "jira_card_link": args.jira_link,
        "polarion_url": args.polarion_url,
        "test_env": {
            "cluster_name": args.cluster_name,
            "nic": args.nic,
            "secondary_nic": args.secondary_nic,
            "cnf_image_version": f"{args.registry_url}/dpdk-base-{rhel_version}:v{args.version}",
            "dpdk_image_version": f"{args.registry_url}/cnf-{rhel_version}:v{args.version}"
        }
    }
    
    message_sent = send_to_slack(args.webhook_url, release_info, prow_job_url)
    if not message_sent:
        logging.error("❌ Error: Slack notification failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
