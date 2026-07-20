#!/usr/bin/env python3
"""
This script is not officially supported and comes with no guarantees.
Use it at your own risk. Test thoroughly in your environment before use.

Download all files from Google Drive folder using service account key.

Environment variables:
  GDRIVE_FOLDER_NAME: Name of the folder to download from (e.g., "SLCM")
  GDRIVE_PARENT_ID: Parent folder/Shared Drive ID where to search
  LOCAL_DOWNLOAD_DIR: Local directory to save files
  GOOGLE_SERVICE_ACCOUNT_KEY: Service account JSON key as string

Requires: pip install pyjwt cryptography

Usage example:
    export GDRIVE_FOLDER_NAME=remote-dir
    export GDRIVE_PARENT_ID=1234567890
    export LOCAL_DOWNLOAD_DIR=/tmp/artifiacts
    export GOOGLE_SERVICE_ACCOUNT_KEY='{"client_email":"service-account@example.com","private_key":"-----BEGIN PRIVATE KEY-----\nMIIE..."}'
    python scripts/slcm/download_from_gdrive.py
"""

from sys import exit, stderr
from json import loads, JSONDecodeError
from time import time
from logging import getLogger, basicConfig, INFO
from os import getenv, path
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode, quote
from urllib.error import HTTPError
from jwt import encode

logger = getLogger(__name__)

GDRIVE_AUTH_SCOPE = "https://www.googleapis.com/auth/drive"
DRIVE_AUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_FILES_API_URL = "https://www.googleapis.com/drive/v3/files"


def get_access_token(service_account_info: dict) -> str:
    """Generate access token from service account key using JWT."""
    now = int(time())

    payload = {
        "iss": service_account_info["client_email"],
        "scope": GDRIVE_AUTH_SCOPE,
        "aud": DRIVE_AUTH_TOKEN_URL,
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
        DRIVE_AUTH_TOKEN_URL,
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


def find_folder_by_name(parent_id: str, folder_name: str, access_token: str) -> str:
    """Find folder by name in parent directory."""
    query = f"name='{folder_name}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    encoded_query = quote(query)

    headers = {"Authorization": f"Bearer {access_token}"}

    request = Request(
        f"{DRIVE_FILES_API_URL}?q={encoded_query}&supportsAllDrives=true&includeItemsFromAllDrives=true&fields=files(id,name)",
        headers=headers,
    )

    try:
        with urlopen(request) as response:
            result = loads(response.read().decode())
            files = result.get("files", [])

            if not files:
                raise Exception(
                    f"Folder '{folder_name}' not found in parent {parent_id}"
                )

            return files[0]["id"]
    except HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise Exception(f"HTTP {e.code}: {error_body}")


def find_folder_by_path(parent_id: str, folder_path: str, access_token: str) -> str:
    """Find folder by path (e.g., 'reports/slcm')."""
    # Split path into parts
    parts = folder_path.strip("/").split("/")

    current_parent = parent_id

    for part in parts:
        logger.info(f"Looking for folder: {part}")
        current_parent = find_folder_by_name(current_parent, part, access_token)

    return current_parent


def list_files_in_folder(folder_id: str, access_token: str) -> list[dict]:
    """List all files and subfolders in a folder recursively."""
    query = f"'{folder_id}' in parents and trashed=false"
    encoded_query = quote(query)

    headers = {"Authorization": f"Bearer {access_token}"}

    request = Request(
        f"{DRIVE_FILES_API_URL}?q={encoded_query}&supportsAllDrives=true&includeItemsFromAllDrives=true&fields=files(id,name,mimeType)",
        headers=headers,
    )

    try:
        with urlopen(request) as response:
            result = loads(response.read().decode())
            return result.get("files", [])
    except HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise Exception(f"HTTP {e.code}: {error_body}")


def download_file(file_id: str, local_path: str, access_token: str) -> bool:
    """Download a file from Google Drive."""
    headers = {"Authorization": f"Bearer {access_token}"}

    request = Request(
        f"{DRIVE_FILES_API_URL}/{file_id}?alt=media&supportsAllDrives=true",
        headers=headers,
    )

    try:
        with urlopen(request) as response:
            with open(local_path, "wb") as f:
                f.write(response.read())
            return True
    except HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise Exception(f"HTTP {e.code}: {error_body}")


def download_folder_recursively(
    folder_id: str, local_dir: Path, access_token: str, current_path: str = ""
) -> tuple[int, int]:
    """Download all files from folder recursively."""
    files = list_files_in_folder(folder_id, access_token)

    downloaded = 0
    failed = 0

    for report_file in files:
        file_name = report_file["name"]
        file_id = report_file["id"]
        mime_type = report_file["mimeType"]

        if mime_type == "application/vnd.google-apps.folder":
            # It's a subfolder - recurse
            subfolder_path = path.join(current_path, file_name)
            subfolder_local = local_dir / subfolder_path
            subfolder_local.mkdir(parents=True, exist_ok=True)

            logger.info(f"Entering folder: {subfolder_path}")
            sub_downloaded, sub_failed = download_folder_recursively(
                file_id, local_dir, access_token, subfolder_path
            )
            downloaded += sub_downloaded
            failed += sub_failed
        else:
            # It's a file - download
            file_path = path.join(current_path, file_name)
            local_file_path = local_dir / file_path

            try:
                download_file(file_id, local_file_path, access_token)
                logger.info(f"Downloaded: {file_path}")
                downloaded += 1
            except Exception as e:
                logger.error(f"Failed to download {file_path}: {e}")
                failed += 1

    return downloaded, failed


def validate_environment(env_var_value: str, env_var_name: str) -> str:
    if not env_var_value:
        logger.error(f"Error: {env_var_name} environment variable not set")
        exit(1)
    return env_var_value


def download_from_gdrive():
    """Main function to download files from Google Drive."""
    # Get configuration from environment
    folder_name = validate_environment(
        getenv("GDRIVE_FOLDER_NAME"), "GDRIVE_FOLDER_NAME"
    )
    parent_id = validate_environment(getenv("GDRIVE_PARENT_ID"), "GDRIVE_PARENT_ID")
    local_dir = validate_environment(getenv("LOCAL_DOWNLOAD_DIR"), "LOCAL_DOWNLOAD_DIR")
    service_account_key = validate_environment(
        getenv("GOOGLE_SERVICE_ACCOUNT_KEY"), "GOOGLE_SERVICE_ACCOUNT_KEY"
    )

    # Parse service account key
    try:
        service_account_info = loads(service_account_key)
    except JSONDecodeError as e:
        logger.error(f"Error: Invalid JSON in GOOGLE_SERVICE_ACCOUNT_KEY: {e}")
        exit(1)

    # Create local directory
    local_dir_path = Path(local_dir)
    local_dir_path.mkdir(parents=True, exist_ok=True)

    # Get access token
    logger.info("Generating access token...")
    try:
        access_token = get_access_token(service_account_info)
    except Exception as e:
        logger.error(f"Error generating access token: {e}")
        exit(1)

    # Find folder by name or path
    logger.info(f"Searching for folder '{folder_name}'...")
    try:
        # Path like "reports/slcm"
        if "/" in folder_name:
            folder_id = find_folder_by_path(parent_id, folder_name, access_token)
        # Simple name like "SLCM"
        else:
            folder_id = find_folder_by_name(parent_id, folder_name, access_token)

        logger.info(f"Found folder: {folder_name}")
    except Exception as e:
        logger.error(f"Error finding folder: {e}")
        exit(1)

    # Download all files
    logger.info(f"Downloading files to {local_dir}...")
    try:
        downloaded, failed = download_folder_recursively(
            folder_id, local_dir_path, access_token
        )
        logger.info(f"\nSummary: {downloaded} downloaded, {failed} failed")

        if failed > 0:
            logger.error(f"Failed to download files")
            exit(1)
    except Exception as e:
        logger.error(f"Error downloading files: {e}")
        exit(1)


def main():
    basicConfig(
        level=INFO,
        format="%(asctime)s %(name)s[%(process)d]: %(levelname)s %(message)s",
        datefmt="%b %d %H:%M:%S",
        stream=stderr,
    )
    download_from_gdrive()


if __name__ == "__main__":
    main()
