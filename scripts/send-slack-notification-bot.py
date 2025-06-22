import requests
import os
import sys
import logging

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

def read_file_content(file_path):
    try:
        with open(file_path, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        logging.warning(f"Warning: File not found at {file_path}. Returning empty string.")
        return ""
    except Exception as e:
        logging.error(f"Error reading file {file_path}: {e}")
        return ""
    
def main():
    webhook_url = os.environ.get("WEBHOOK_URL")
    shared_dir = os.environ.get("SHARED_DIR")
    registry_url = os.environ.get("REGISTRY_URL", "https://registry.stage.redhat.io/openshift4")
    prow_job_url = os.environ.get("JOB_URL", "Job URL Not Available") 
    
    if not webhook_url or not shared_dir:
        logging.error("❌ Error: WEBHOOK_URL and SHARED_DIR environment variables must be set")
        sys.exit(1)
    
    version = read_file_content(os.path.join(shared_dir, "cluster_version"))
    if not version:
        logging.error("❌ Error: Could not read version from cluster_version file.")
        sys.exit(1)

    # Determine RHEL version based on the cluster version
    rhel_version = "rhel9"  # Default to rhel9
    try:
        # Compare version as a tuple of integers, e.g., (4, 14) <= (4, 15)
        major, minor, *_ = map(int, version.split('.'))
        if (major, minor) <= (4, 15):
            rhel_version = "rhel8"
        logging.info(f"Detected version {version}, using '{rhel_version}' images.")
    except (ValueError, IndexError):
        logging.error(f"❌ Error: Invalid version format: '{version}'. Expected 'major.minor.patch'.")
        sys.exit(1)  
        
    release_info = {
        "version": version,
        "jira_card_link": read_file_content(os.path.join(shared_dir, "jira_link")),
        "test_env": {
            "cluster_name": read_file_content(os.path.join(shared_dir, "cluster_name")),
            "nic": read_file_content(os.path.join(shared_dir, "ocp_nic")),
            "secondary_nic": read_file_content(os.path.join(shared_dir, "secondary_nic")),
            "cnf_image_version": f"{registry_url}/dpdk-base-{rhel_version}:v{version}",
            "dpdk_image_version": f"{registry_url}/cnf-{rhel_version}:v{version}"
        }
    }
    
    message_sent = send_to_slack(webhook_url, release_info, prow_job_url)
    if not message_sent:
        logging.error("❌ Error: Slack notification failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
