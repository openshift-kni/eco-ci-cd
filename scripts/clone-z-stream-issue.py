import logging
import os
from jira import JIRA

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


# Initialize JIRA client with Bearer token
def init_jira_client(server_url, bearer_token):
    """
    Create JIRA client with Bearer authentication.
    
    Args:
        server_url (str): Jira server URL
        bearer_token (str): Your Bearer token
    
    Returns:
        JIRA: Configured JIRA client
    """
    
    try: 
        # Base headers with Bearer authentication
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # JIRA client options
        options = {
            'server': server_url,
            'headers': headers
        }
        
        logging.info(f"Attempting to connect to Jira server: {server_url}")
        jira = JIRA(options)
        logging.info("JIRA client successfully initialized")
        return jira
    
    except Exception as e:
        logging.error(f"Unexpected error while creating Jira client: {e.stderr}")
        exit(1)

def get_env(env_var_name: str) -> str:
    value = getenv(env_var_name)
    if not value:
        logging.error(f"Environment variable {env_var_name} is required.")
        exit(1)
        
    return value


def main():

    logging.info(f"\n--- Get Jira Issue and Clone it ---")
    
    z_stream_version = get_env("Z_STREAM_VERSION")
    jira_token = get_env("JIRA_TOKEN")

    jira_client = init_jira_client("https://issues.redhat.com", jira_token)
    issue_to_clone = jira_client.issue("CNF-3244")
    
    new_issue_fields = {
        'project': {'key': issue_to_clone.fields.project.key},
        'issuetype': {'name': issue_to_clone.fields.issuetype.name},
        'description': issue_to_clone.fields.description,
        'summary': f'QE Zstream Verification Release {z_stream_version}'
    }
    
    cloned_issue = jira_client.create_issue(fields=new_issue_fields)
    
    logging.info(f"\nSuccessfully cloned issue '{issue_to_clone.key}'")
    logging.info(f"New cloned issue key: {cloned_issue.key}")
    logging.info(f"New cloned issue summary: {cloned_issue.fields.summary}")
    logging.info(f"View new issue at: {cloned_issue.permalink()}")

if __name__ == "__main__":
    main()
