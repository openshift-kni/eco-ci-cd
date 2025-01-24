# OCP Version Facts Ansible Role

## Disclaimer
This role is provided as-is, without any guarantees of support or maintenance.  
The author or contributors are not responsible for any issues arising from the use of this role. Use it at your own discretion.

## Overview
The `ocp_version_facts` Ansible role is responsible for managing and setting OpenShift Container Platform (OCP) version-related facts. It ensures that necessary version information is properly parsed, validated, and available for further automation tasks.

## Features
- Determines the OCP version type (using full pull spec or short release as input).
- Sets major, minor, and z-stream versions.
- Identifies and sets development versions when present.
- Ensures all required version facts are configured.
- Provides debug output for all configured facts.

## Requirements
- Ansible 2.9+
- Supported Platforms:
  - RHEL 7/8
  - CentOS 7/8

## Role Variables
The following variables are used within the role:

- `ocp_version_facts_release`: Release version provided as input (e.g., `4.17.1`,`4.15`, `quay.io/openshift-release-dev/ocp-release:4.15.1-x86_64`).
- `ocp_version_facts_parsed_release`: Parsed release version (e.g., `4.17.1`).
- `ocp_version_facts_pull_spec`: Pull spec for the OCP image.
- `ocp_version_facts_major`: Major version number (e.g., `4`).
- `ocp_version_facts_minor`: Minor version number (e.g., `17`).
- `ocp_version_facts_z_stream`: Z-stream version number (e.g., `2`).
- `ocp_version_facts_dev_version`: Development version if present (e.g., `rc1`).
- `ocp_version_facts_oc_client_pull_link`: Link to pull the OC client.

## Usage
To use this role, include it in your playbook as follows:

```yaml
- hosts: localhost
  roles:
    - role: ocp_version_facts
      vars:
        ocp_version_facts_release: "4.17.1"
```
## Tasks Description

### Set facts for provided pull spec

Includes a task file if a full pull spec is provided. The `pull-spec-provided.yml` file performs the following tasks:

- Sets the pull spec.
- Extracts the release version from the pull spec using regex.
- Constructs the OC client pull link using artifacts link and client prefix.

### Set facts for short release version

Includes a task file for short release versions. The `version-provided.yml` file performs the following tasks:

- Fetches data from a JSON API.
- Queries and filters for the accepted release version.
- Sets the pull spec, parsed release version, and OC client pull link from the API response.

### Set major/minor/z_stream versions

Extracts and sets the major, minor, and z-stream versions.

### Set dev version if present and remove z-stream

Identifies and sets development versions.

### Assert required facts

Ensures all necessary facts are configured properly.

### Display ocp_version_facts

Outputs debug information for configured facts.

## Dependencies

None.

## Example Playbook

```yaml
- hosts: localhost
  gather_facts: no
  roles:
    - role: ocp_version_facts
      vars:
        ocp_version_facts_release: "quay.io/openshift-release-dev/ocp-release:4.8.0-x86_64"
```
## License

Apache

## Author Information

This role was created by Nikita Kononov.