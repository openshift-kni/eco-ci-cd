import logging
import os
import sys
import argparse
from jira import JIRA

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

def init_jira_client(server_url, api_token):
    """Create JIRA client with Basic authentication (email + API token)."""
    try:
        email = os.environ.get("JIRA_EMAIL", "sobarzan@redhat.com")

        logging.info(f"Attempting to connect to Jira server: {server_url}")
        jira = JIRA(server=server_url, basic_auth=(email, api_token))
        logging.info("✅ JIRA client successfully initialized")
        return jira
    
    except Exception as e:
        logging.error(f"❌ Unexpected error while creating Jira client: {e}")
        sys.exit(1)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Clone a JIRA issue for Z-stream verification")
    
    # Required arguments 
    parser.add_argument("--z-stream-version", help="Z-stream version")
    parser.add_argument("--jira-token", help="JIRA authentication token")
    parser.add_argument("--shared-dir", help="Shared directory path")
    
    # Optional arguments with defaults
    parser.add_argument("--jira-issue", default="CNF-3244", help="JIRA issue key to clone (default: %(default)s)")
    parser.add_argument("--assignee", default="elevin@redhat.com", help="Assignee for the new issue (default: %(default)s)")
    parser.add_argument("--jira-server", default="https://redhat.atlassian.net", help="JIRA server URL (default: %(default)s)")
    return parser.parse_args()

CONTRIBUTORS = ["ajaggapa@redhat.com", "gkopels@redhat.com", "elevin@redhat.com"]

def get_account_id_by_email(jira_client, identifier):
    """Resolve an email or username to a Jira Cloud accountId."""
    if not identifier:
        return None
    users = jira_client.search_users(query=identifier, maxResults=1)
    if users:
        return users[0].accountId
    logging.warning(f"⚠️  Could not resolve user: {identifier}")
    return None

def create_issue_fields(jira_client, original_issue, z_stream_version, assignee):
    """Create the fields dictionary for the new cloned issue."""
    fields = {
        'project': {'key': original_issue.fields.project.key},
        'issuetype': {'name': original_issue.fields.issuetype.name},
        'description': original_issue.fields.description,
        'summary': f'QE Zstream Verification Release {z_stream_version}',
    }
    account_id = get_account_id_by_email(jira_client, assignee)
    if account_id:
        fields['assignee'] = {'accountId': account_id}
    return fields

def add_contributors(jira_client, issue, contributors):
    """Set contributors on the issue using the contributors custom field."""
    try:
        accounts = []
        for c in contributors:
            account_id = get_account_id_by_email(jira_client, c.strip())
            if account_id:
                accounts.append({'accountId': account_id})
        if not accounts:
            return
        issue.update(fields={'customfield_10466': accounts})
    except Exception as e:
        logging.warning(f"⚠️  Could not set contributors: {e}")

def clone_jira_issue(jira_client, jira_issue, z_stream_version, assignee, shared_dir):
    """Clone a JIRA issue and save the link."""
    try:
        # Get the original issue
        logging.info(f"Fetching original issue: {jira_issue}")
        issue_to_clone = jira_client.issue(jira_issue)
        logging.info(f"✅ Successfully fetched issue: {issue_to_clone.key}")

        # Create new issue fields
        new_issue_fields = create_issue_fields(jira_client, issue_to_clone, z_stream_version, assignee)

        # Create the cloned issue
        logging.info("Creating cloned issue...")
        cloned_issue = jira_client.create_issue(fields=new_issue_fields)

        # Set story points to 1
        logging.info("Setting story points...")
        cloned_issue.update(fields={'customfield_10028': 1})
        logging.info("✅ Story points set to 1")

        # Add contributors
        logging.info(f"Setting contributors: {CONTRIBUTORS}")
        add_contributors(jira_client, cloned_issue, CONTRIBUTORS)

        # Save the jira link to a file for slack notification
        jira_link_path = os.path.join(shared_dir, "jira_link")
        with open(jira_link_path, "w") as f:
            f.write(cloned_issue.permalink())

        # Log success information
        logging.info(f"✅ Successfully cloned issue '{issue_to_clone.key}'")
        logging.info(f"📋 New cloned issue key: {cloned_issue.key}")
        logging.info(f"📝 New cloned issue summary: {cloned_issue.fields.summary}")
        logging.info(f"🔗 View new issue at: {cloned_issue.permalink()}")

        return True

    except Exception as e:
        logging.error(f"❌ Unable to clone issue: {e}")
        return False

def main():
    """Main function to orchestrate the JIRA issue cloning process."""
    args = parse_arguments()
    
    # Resolve configuration - CLI args override environment variables
    z_stream_version = args.z_stream_version or os.environ.get("Z_STREAM_VERSION")
    jira_token = args.jira_token or os.environ.get("JIRA_TOKEN")
    shared_dir = args.shared_dir or os.environ.get("SHARED_DIR")

    # Check required values
    if not z_stream_version:
        logging.error("❌ Z-stream version is required. Provide via --z-stream-version or Z_STREAM_VERSION env var.")
        sys.exit(1)

    if not jira_token:
        logging.error("❌ JIRA token is required. Provide via --jira-token or JIRA_TOKEN env var.")
        sys.exit(1)

    if not shared_dir:
        logging.error("❌ Shared directory is required. Provide via --shared-dir or SHARED_DIR env var.")
        sys.exit(1)
    
    # Initialize JIRA client
    jira_client = init_jira_client(args.jira_server, jira_token)
    
    # Clone the issue
    success = clone_jira_issue(jira_client, args.jira_issue, z_stream_version, args.assignee, shared_dir)
    
    if not success:
        logging.error("❌ Error: JIRA issue cloning failed.")
        sys.exit(1)
    
    logging.info("✅ JIRA issue cloning completed successfully!")

if __name__ == "__main__":
    main()
