# SLCM Google Drive Scripts

Utilities for uploading and downloading XML test reports to and from Google Drive as part of SLCM workflows.

## `upload_to_gdrive.py`

Uploads XML files from a local directory to Google Drive, then triggers a downstream CI job via the API.

### What it does

1. Authenticates to Google Drive using a service account JSON key (JWT bearer flow).
2. Recursively finds all `.xml` files under `LOCAL_XML_REPORT_DIR`.
3. Creates a subfolder named after `JOB_NAME` under the target Drive folder (`GDRIVE_FOLDER_ID`). If a folder with that name already exists, it is moved to trash and recreated.
4. Uploads each XML file into that subfolder.
5. Triggers a job execution via `API_URL`, passing `JOB_NAME` and optional pod environment overrides.

### Prerequisites

- Python 3
- Dependencies: `pyjwt`, `cryptography` (listed in `pip.txt`)

```bash
pip install pyjwt cryptography
```

- A Google Cloud service account with Drive API access
- The target Google Drive folder shared with the service account email (`client_email` from the JSON key)

### Google Drive setup

1. Create or select a Google Cloud service account and download its JSON key.
2. Enable the Google Drive API for the project.
3. Create or choose a Drive folder and share it with the service account email (Editor access).
4. Copy the folder ID from the URL: `https://drive.google.com/drive/folders/<FOLDER_ID>`

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LOCAL_XML_REPORT_DIR` | Yes | Local directory containing XML files to upload (searched recursively) |
| `GDRIVE_FOLDER_ID` | Yes | Google Drive parent folder ID |
| `GOOGLE_SERVICE_ACCOUNT_KEY` | Yes | Service account JSON key as a single-line string |
| `JOB_NAME` | Yes | Name of the CI job; also used as the subfolder name in Drive |
| `API_URL` | Yes | API endpoint URL for triggering job execution |
| `TOKEN` | Yes | Bearer token for authenticating to the API |

### Usage

```bash
export LOCAL_XML_REPORT_DIR=/tmp/xml-reports
export GDRIVE_FOLDER_ID=1234567890abcdef
export GOOGLE_SERVICE_ACCOUNT_KEY='{"type":"service_account","client_email":"service-account@project.iam.gserviceaccount.com","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",...}'
export JOB_NAME=periodic-job-name
export API_URL=https://example.com/api/v1/job/execute
export TOKEN=your-bearer-token

python scripts/slcm/upload_to_gdrive.py
```

### Running from container

Mount the local reports directory into the container and pass the required environment variables:

```bash
podman run -it --rm --entrypoint python3 \
    -v /tmp/reports:/tmp/reports:Z \
    -e LOCAL_XML_REPORT_DIR=/tmp/reports \
    -e GDRIVE_FOLDER_ID=123456789000000x \
    -e GOOGLE_SERVICE_ACCOUNT_KEY='{"type":"service_account"....}' \
    -e JOB_NAME=periodic-job-name \
    -e TOKEN='1234567890abc' \
    -e API_URL='https://example.com/api/v1/job/execute' \
    quay.io/telcov10n-ci/eco-ci-cd:latest /eco-ci-cd/scripts/slcm/upload_to_gdrive.py
```

The `:Z` volume flag sets the correct SELinux context for the mounted directory.

### Exit codes

- `0` — All XML files uploaded successfully and the downstream job was triggered.
- `1` — Missing or invalid configuration, authentication failure, one or more upload failures, or job trigger failure after retries.

### Logging

Logs are written to stderr with timestamps. A summary line reports how many files were uploaded and how many failed.

### Related script

See [`download_from_gdrive.py`](download_from_gdrive.py) for downloading files from a Google Drive folder.
