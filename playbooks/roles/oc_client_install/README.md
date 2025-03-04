## OpenShift Client (OC) Installation Ansible Role

## Disclaimer
This role is provided as-is, without any guarantees of support or maintenance.  
The author or contributors are not responsible for any issues arising from the use of this role. Use it at your own discretion.

### Overview
This Ansible role automates the installation and management of the OpenShift Client (`oc`). It verifies if the client is installed, removes any existing versions, and deploys the latest specified version.

### Features
- Verifies if the `oc_client_install_url` variable is provided.
- Checks if `oc` is already installed.
- Removes existing `oc` binary if found.
- Downloads and installs the `oc` client either from mirror or from the specified source.
- Ensures proper directory structure for the `oc` binary.
- Moves both `oc` and `kubectl` binaries to the user's `.local/bin` directory.
- Verifies the installation by running `oc version`.

### Requirements
- Ansible 2.9+
- Supported Platforms:
  - RHEL 7/8
  - CentOS 7/8
  - Fedora
  - Ubuntu/Debian

### Role Variables

| Variable | Description | Required|
|----------|-------------|---------|
| `oc_client_install_url` | URL to download the OpenShift client archive (Required) |yes|
| `oc_client_install_archive_dest_dir` | Directory where the archive will be stored |no|
| `oc_client_install_archive_name` | Name of the downloaded archive file |no|
| `oc_clinet_install_version` | Specifies the OC client version used for retrieving the archive from the mirror link |no|

### Usage
Include this role in your playbook as follows:

```yaml
- hosts: localhost
  gather_facts: no
  roles:
    - role: oc_client_install
      vars:
        oc_client_install_url: "https://mirror.openshift.com/pub/openshift-v4/x86_64/clients/ocp/latest/openshift-client-linux.tar.gz"
```

### Tasks Description

#### `main.yml`
1. **Verify Client URL is Provided**  
   Ensures the `oc_client_install_url` variable is set; otherwise, the role fails.

2. **Check if `oc` is Installed**  
   Runs `which oc` to determine if the `oc` binary is already present.

3. **Remove Pre-existing `oc` Client**  
   Includes `oc_remove.yml` to find and remove any existing `oc` binaries.

4. **Deploy `oc` Client**  
   Includes `oc_install.yml` to download, extract, and install the `oc` client.

#### `oc_install.yml`
1. **Trigger Tools Extraction**  
   Makes a request to the base URL of the provided OpenShift client URL.

2. **Remove Pre-existing Archive**  
   Ensures any previously downloaded archive is removed before downloading.

3. **Download OpenShift Client Archive**  
   Fetches the `openshift-client-linux.tar.gz` file either from the mirror or from the given URL.

4. **Extract Archive**  
   Unpacks the downloaded archive.

5. **Ensure Required Directories Exist**  
   Creates `~/.local/bin` if it does not exist.

6. **Move `oc` and `kubectl` Binaries**  
   Moves extracted binaries to `~/.local/bin`.

7. **Verify Installation**  
   Runs `oc version` to confirm the binary is correctly installed and executable.

8. **Fail if `oc` is Missing**  
   Aborts execution if `oc` is not found or not executable.

#### `oc_remove.yml`
1. **Search for Existing `oc` Binaries**  
   Searches common directories (`/usr/local/bin`, `/usr/bin`, `/opt/bin`, `~/.local/bin`, `/tmp`) for `oc` binaries.

2. **Remove Existing `oc` Binaries**  
   Deletes all found `oc` binaries to ensure a fresh installation.

### Dependencies
None.

### Example Playbook
```yaml
- hosts: localhost
  gather_facts: no
  roles:
    - role: oc_client_install
      vars:
        oc_client_install_url: "https://mirror.openshift.com/pub/openshift-v4/x86_64/clients/ocp/latest/openshift-client-linux.tar.gz"
```
Example of getting client from the mirror first:
```yaml
- hosts: localhost
  gather_facts: no
  roles:
    - name: Deploy/Redeploy OCP client
      ansible.builtin.import_role:
        name: oc_client_install
      vars:
        oc_client_install_url: "https://mirror.openshift.com/pub/openshift-v4/x86_64/clients/ocp/latest/"
        oc_client_install_archive_dest_dir: "/tmp/client"
        oc_clinet_install_version: "4.17.10"
```
### License
Apache

### Author Information
This role was created by Nikita Kononov.
