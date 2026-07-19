#!/usr/bin/env python3
"""
Upload XML files to Google Drive using service account key.

Environment variables:
  XML_DIR: Directory containing XML files to upload
  GDRIVE_FOLDER_ID: Google Drive folder ID (from folder URL)
  GOOGLE_SERVICE_ACCOUNT_KEY: Service account JSON key as string

Setup:
  1. Share a Drive folder with the service account email
  2. Get folder ID from URL: drive.google.com/drive/folders/FOLDER_ID
  3. Store service account JSON as env var

Requires: pip install pyjwt cryptography

Usage example:
    export LOCAL_XML_REPORT_DIR=/tmp/xml-reports
    export GDRIVE_FOLDER_ID=1234567890
    export GOOGLE_SERVICE_ACCOUNT_KEY='{"client_email":"service-account@example.com","private_key":"-----BEGIN PRIVATE KEY-----\nMIIE..."}'
    export JOB_NAME=periodic-job-name
    export API_URL=https://link.to.ci.api
    export TOKEN=bearer-token-for-ci-api
    python scripts/slcm/upload_to_gdrive.py
"""

from os import getenv
from sys import exit, stderr
from json import loads, dumps, JSONDecodeError
from time import time, sleep
from logging import getLogger, basicConfig, INFO
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError
from jwt import encode

logger = getLogger(__name__)
DRIVE_AUTH_API_URL = "https://www.googleapis.com/auth/drive"
DRIVE_API_URL = "https://www.googleapis.com/upload/drive/v3"
GDRIVE_API_URL = "https://www.googleapis.com/drive/v3/files"
OAUTH2_API_URL = "https://oauth2.googleapis.com/token"


def set_headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def create_folder(parent_id: str, folder_name: str, access_token: str) -> str:
    """Create a folder in Google Drive."""
    metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }

    headers = set_headers(access_token)

    request = Request(
        f"{GDRIVE_API_URL}?supportsAllDrives=true",
        data=dumps(metadata).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urlopen(request) as response:
            result = loads(response.read().decode())
            return result.get("id")
    except HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise Exception(f"HTTP {e.code}: {error_body}")


def find_or_create_folder(parent_id: str, folder_name: str, access_token: str) -> str:
    """Find existing folder or create new one."""
    from urllib.parse import quote

    query = f"name='{folder_name}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    encoded_query = quote(query)

    headers = set_headers(access_token)
    # headers = {
    #     'Authorization': f'Bearer {access_token}'
    # }

    request = Request(
        f"{GDRIVE_API_URL}?q={encoded_query}&fields=files(id,name,capabilities)&supportsAllDrives=true&includeItemsFromAllDrives=true",
        headers=headers,
    )

    try:
        with urlopen(request) as response:
            result = loads(response.read().decode())
            files = result.get("files", [])
            if files:
                folder = files[0]
                logger.info(
                    f"Found existing folder '{folder_name}': ID={folder['id']}, capabilities={folder.get('capabilities')}"
                )

                # Try to delete
                if trash_gdrive_folder(folder["id"], access_token):
                    logger.info(f"Successfully deleted folder: {folder_name}")
                else:
                    logger.error(
                        f"Failed to delete folder {folder_name}, but continuing to create new one"
                    )

            return create_folder(parent_id, folder_name, access_token)
    except HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise Exception(f"HTTP {e.code}: {error_body}")


def get_access_token(service_account_info: dict) -> str:
    """Generate access token from service account key using JWT."""
    now = int(time())

    payload = {
        "iss": service_account_info["client_email"],
        "scope": DRIVE_AUTH_API_URL,
        "aud": OAUTH2_API_URL,
        "iat": now,
        "exp": now + 3600,
    }

    # Sign JWT with private key
    signed_jwt = encode(payload, service_account_info["private_key"], algorithm="RS256")

    # Exchange JWT for access token
    data = urlencode(
        {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": signed_jwt,
        }
    ).encode()

    request = Request(
        OAUTH2_API_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with urlopen(request) as response:
            result = loads(response.read().decode())
            return result["access_token"]
    except HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise Exception(f"Failed to get access token: {error_body}")


def upload_file_to_drive(folder_id: str, file_path: Path, access_token: str) -> str:
    """Upload a file to Google Drive folder."""
    file_name = file_path.name

    # Step 1: Create file metadata
    metadata = {"name": file_name, "parents": [folder_id]}

    # Step 2: Upload file using multipart upload
    boundary = "-------314159265358979323846"

    with open(file_path, "rb") as f:
        file_content = f.read()

    # Build multipart body
    body_parts = [
        f"--{boundary}",
        "Content-Type: application/json; charset=UTF-8",
        "",
        dumps(metadata),
        f"--{boundary}",
        "Content-Type: application/xml",
        "",
        file_content.decode("utf-8", errors="replace"),
        f"--{boundary}--",
    ]

    body = "\r\n".join(str(part) for part in body_parts).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": f"multipart/related; boundary={boundary}",
        "Content-Length": str(len(body)),
    }

    request = Request(
        f"{DRIVE_API_URL}/files?uploadType=multipart&supportsAllDrives=true",
        data=body,
        headers=headers,
        method="POST",
    )

    try:
        with urlopen(request) as response:
            result = loads(response.read().decode())
            return result.get("id")
    except HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise Exception(f"HTTP {e.code}: {error_body}")


def validate_environment(env_var_value: str, env_var_name: str) -> str:
    if not env_var_value:
        logger.error(f"Error: {env_var_name} environment variable not set")
        exit(1)
    return env_var_value


def upload_xml_files():
    # Get configuration from environment
    xml_dir = validate_environment(
        getenv("LOCAL_XML_REPORT_DIR"), "LOCAL_XML_REPORT_DIR"
    )
    folder_id = validate_environment(getenv("GDRIVE_FOLDER_ID"), "GDRIVE_FOLDER_ID")
    service_account_key = validate_environment(
        getenv("GOOGLE_SERVICE_ACCOUNT_KEY"), "GOOGLE_SERVICE_ACCOUNT_KEY"
    )
    job_name = validate_environment(getenv("JOB_NAME"), "JOB_NAME")

    # Parse service account key
    try:
        service_account_info = loads(service_account_key)
    except JSONDecodeError as e:
        logger.error(
            f"Error: Invalid JSON in GOOGLE_SERVICE_ACCOUNT_KEY: {e}", file=stderr
        )
        exit(1)

    xml_dir_path = Path(xml_dir)

    if not xml_dir_path.exists():
        logger.error(f"Error: Directory {xml_dir} does not exist", file=stderr)
        exit(1)

    if not xml_dir_path.is_dir():
        logger.error(f"Error: {xml_dir} is not a directory", file=stderr)
        exit(1)

    # Get access token
    logger.info("Generating access token...")
    try:
        access_token = get_access_token(service_account_info)
    except Exception as e:
        logger.error(f"Error generating access token: {e}", file=stderr)
        exit(1)

    # Find all XML files recursively
    xml_files = list(xml_dir_path.glob("**/*.xml"))

    if not xml_files:
        logger.error(f"No XML files found in {xml_dir}")
        return

    logger.info(f"Found {len(xml_files)} XML file(s) in {xml_dir}")

    # Upload each file
    uploaded = 0
    failed = 0

    folder_id = find_or_create_folder(folder_id, job_name, access_token)
    for xml_file in xml_files:
        try:
            file_id = upload_file_to_drive(folder_id, xml_file, access_token)
            logger.info(f"Uploaded: {xml_file.name} (ID: {file_id})")
            uploaded += 1
        except Exception as e:
            logger.error(f"Failed to upload {xml_file.name}: {e}", file=stderr)
            failed += 1

    logger.info(f"Summary: {uploaded} uploaded, {failed} failed")

    if failed > 0:
        exit(1)


def trash_gdrive_folder(folder_id: str, access_token: str) -> bool:
    """Trash a folder in Google Drive (moves to trash)."""
    headers = set_headers(access_token)

    # Update the folder to set trashed=true
    data = dumps({"trashed": True}).encode("utf-8")

    request = Request(
        f"{GDRIVE_API_URL}/{folder_id}?supportsAllDrives=true",
        data=data,
        headers=headers,
        method="PATCH",
    )

    try:
        with urlopen(request) as response:
            logger.info(f"Trashed folder if it exists")
            return True
    except HTTPError as e:
        if e.code == 404:
            logger.warning(f"Folder not found, skipping trash")
            return False
        error_body = e.read().decode("utf-8")
        raise Exception(f"HTTP {e.code}: {error_body}")


def trigger_job_execution(job_execution_type: str = "1", envs: dict = None) -> dict:
    """
    Trigger a job execution via Gangway API.

    Args:
        token: Bearer token for authentication
        job_name: Name of the job to execute
        job_execution_type: Execution type (default "1")
        envs: Dictionary of environment variables to override

    Returns:
       Response JSON as dict

    Raises:
        Exception: If the API request fails after 3 retries
    """
    # Build payload
    token = validate_environment(getenv("TOKEN"), "TOKEN")
    job_name = validate_environment(getenv("JOB_NAME"), "JOB_NAME")
    api_url = validate_environment(getenv("API_URL"), "API_URL")

    payload = {"job_name": job_name, "job_execution_type": job_execution_type}

    if envs:
        payload["pod_spec_options"] = {"envs": envs}

    # Headers
    headers = set_headers(token)

    # Retry logic: 3 attempts with 1 minute delay
    max_retries = 3
    retry_delay = 60  # seconds

    for attempt in range(1, max_retries + 1):
        try:
            # Create request
            request = Request(
                api_url,
                data=dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )

            # Execute request
            with urlopen(request) as response:
                if response.status == 200:
                    result = loads(response.read().decode("utf-8"))
                    return result
                else:
                    error_msg = (
                        f"HTTP {response.status}: {response.read().decode('utf-8')}"
                    )
                    if attempt < max_retries:
                        logger.warning(
                            f"Attempt {attempt} failed: {error_msg}. Retrying in {retry_delay} seconds..."
                        )
                        sleep(retry_delay)
                    else:
                        logger.error(
                            f"Failed after {max_retries} attempts: {error_msg}"
                        )
                        raise Exception(
                            f"Failed after {max_retries} attempts: {error_msg}"
                        )

        except HTTPError as e:
            error_body = e.read().decode("utf-8")
            error_msg = f"HTTP {e.code}: {error_body}"

            if attempt < max_retries:
                logger.warning(
                    f"Attempt {attempt} failed: {error_msg}. Retrying in {retry_delay} seconds..."
                )
                sleep(retry_delay)
            else:
                raise Exception(f"Failed after {max_retries} attempts: {error_msg}")
        except Exception as e:
            if attempt < max_retries:
                logger.warning(
                    f"Attempt {attempt} failed: {str(e)}. Retrying in {retry_delay} seconds..."
                )
                sleep(retry_delay)
            else:
                raise Exception(f"Failed after {max_retries} attempts: {str(e)}")


def main():
    basicConfig(
        level=INFO,
        format="%(asctime)s %(name)s[%(process)d]: %(levelname)s %(message)s",
        datefmt="%b %d %H:%M:%S",
        stream=stderr,
    )
    upload_xml_files()
    trigger_job_execution()


if __name__ == "__main__":
    main()
