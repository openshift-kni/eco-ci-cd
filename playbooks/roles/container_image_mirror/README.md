# Container Image Mirror Ansible Role

## Disclaimer
This role is provided as-is, without guarantees of support or maintenance.
Use at your own discretion.

## Overview
The `container_image_mirror` role provides generic container image mirroring and removal capabilities for internal registries. It uses `skopeo` to:
- **Mirror** container images from source registries to a target internal registry
- **Remove** container images from an internal registry

This role is designed to work with any container registry and supports both connected and disconnected (air-gapped) environments.

## Features
- Generic image mirroring using `skopeo copy`
- Image removal from registry storage
- Pull secret support for private registries
- Configurable TLS verification
- Detailed success/failure reporting with summary
- Idempotent operations with existence checks
- Continues mirroring all images even if some fail
- Per-image success/failure tracking

## Requirements
- Ansible 2.9+
- Tools available on the target host:
  - `skopeo` (for mirroring operations)
- For removal operations:
  - `sudo` access to registry storage path
- Target registry must be reachable
- Pull secrets for source registries (if private)

## Role Variables

### Required Variables

- **`container_image_mirror_images`** (list): List of image mappings
  - For mirror operation: `[{"source": "quay.io/org/image:tag", "dest": "namespace/image:tag"}]`
  - For remove operation: `[{"dest": "namespace/image:tag"}]`
  - No default (must be provided)

### Optional Variables

- **`container_image_mirror_operation`** (string): Operation mode
  - Values: `mirror` or `remove`
  - Default: `mirror`

- **`container_image_mirror_registry_host`** (string): Target registry hostname
  - Default: `{{ ansible_fqdn }}`

- **`container_image_mirror_registry_port`** (int): Target registry port
  - Default: `5000`

- **`container_image_mirror_registry_namespace`** (string): Namespace prefix for destination images
  - Default: `""` (empty, no prefix)
  - Example: `ran-test/` would prefix all destination images

- **`container_image_mirror_dest_tls_verify`** (bool): Verify TLS for destination registry
  - Default: `false`

- **`container_image_mirror_use_pull_secret`** (bool): Enable pull secret file authentication
  - Default: `false`
  - When `false`: skopeo uses system authentication from `/etc/containers/auth.json`
  - When `true`: skopeo uses pull secret file via `--authfile` parameter

- **`container_image_mirror_pull_secret_string`** (string): Base64-encoded pull secret JSON
  - Default: `""` (empty, uses existing auth)
  - Format: Base64-encoded Docker config JSON
  - Only used when `container_image_mirror_use_pull_secret=true`

- **`container_image_mirror_pull_secret_path`** (string): Path to store pull secret
  - Default: `/tmp/.pull-secret-mirror.json`
  - Only used when `container_image_mirror_use_pull_secret=true`

- **`container_image_mirror_registry_data_path`** (string): Registry storage path (for removal)
  - Default: `/home/kni/registry/data/docker/registry/v2/repositories`

## Dependencies
None.

## Authentication Methods

The role supports two authentication methods:

### System Authentication (Recommended)

When `use_pull_secret=false` (default), skopeo uses system authentication from `/etc/containers/auth.json`. This is the recommended approach when:
- Source registries are public
- Authentication has been configured beforehand (e.g., via `podman login` or `authWithQuay()` in Jenkins)
- Both source and destination credentials are in the system auth file

### Pull Secret File Authentication

When `use_pull_secret=true`, skopeo uses a dedicated pull secret file via the `--authfile` parameter. Use this when:
- You need to use specific credentials different from system auth
- Working with private registries requiring explicit authentication
- Credentials should not persist in system auth

**Important**: When using pull secrets, the content is never logged and the file is automatically cleaned up after use.

## Example Playbooks

### Mirror Images with System Authentication (Recommended)

```yaml
---
- name: Mirror RAN test images to internal registry
  hosts: bastion
  gather_facts: true
  roles:
    - role: container_image_mirror
      vars:
        container_image_mirror_operation: mirror
        container_image_mirror_registry_host: disconnected.registry.local
        container_image_mirror_registry_port: 5000
        container_image_mirror_registry_namespace: ran-test/
        container_image_mirror_images:
          - source: quay.io/telcov10n-ci/oslat:latest
            dest: oslat:latest
          - source: quay.io/telcov10n-ci/cyclictest:latest
            dest: cyclictest:latest
          - source: quay.io/telcov10n-ci/cnf-tests:4.8
            dest: cnf-tests:4.8
```

### Mirror Images with Pull Secret

```yaml
---
- name: Mirror private images to internal registry
  hosts: bastion
  gather_facts: true
  roles:
    - role: container_image_mirror
      vars:
        container_image_mirror_operation: mirror
        container_image_mirror_registry_host: registry.example.com
        container_image_mirror_use_pull_secret: true
        container_image_mirror_pull_secret_string: "{{ pull_secret }}"
        container_image_mirror_images:
          - source: quay.io/private-org/image:tag
            dest: namespace/image:tag
```

### Remove Images Example

```yaml
---
- name: Remove old RAN test images from internal registry
  hosts: bastion
  gather_facts: true
  roles:
    - role: container_image_mirror
      vars:
        container_image_mirror_operation: remove
        container_image_mirror_registry_namespace: ran-test/
        container_image_mirror_images:
          - dest: oslat:old-version
          - dest: cyclictest:deprecated
```

## Usage

### Via Playbook

Create a playbook that includes the role:

```yaml
---
- name: Mirror container images
  hosts: bastion
  gather_facts: true
  vars:
    images_to_mirror:
      - source: quay.io/org/app:v1.0
        dest: apps/app:v1.0
  roles:
    - role: container_image_mirror
      vars:
        container_image_mirror_operation: mirror
        container_image_mirror_images: "{{ images_to_mirror }}"
```

### Command Line

```bash
ansible-playbook mirror-images-playbook.yml \
  -i inventories/ocp-deployment/build-inventory.py \
  --extra-vars "container_image_mirror_pull_secret_string=$(cat ~/.docker/config.json | base64 -w0)"
```

## Output Examples

### Successful Mirror

```
TASK [container_image_mirror : Display detailed mirror results]
ok: [bastion] => {
    "msg": [
        "==========================================",
        "MIRROR SUMMARY",
        "==========================================",
        "Total images: 3",
        "Successfully mirrored: 3",
        "Failed: 0",
        "",
        "SUCCESSFUL:",
        "  ✓ oslat:latest",
        "  ✓ cyclictest:latest",
        "  ✓ cnf-tests:4.8",
        "",
        "FAILED:",
        "  (none)",
        "=========================================="
    ]
}
```

### Partial Failure

```
TASK [container_image_mirror : Display detailed mirror results]
ok: [bastion] => {
    "msg": [
        "==========================================",
        "MIRROR SUMMARY",
        "==========================================",
        "Total images: 3",
        "Successfully mirrored: 2",
        "Failed: 1",
        "",
        "SUCCESSFUL:",
        "  ✓ oslat:latest",
        "  ✓ cyclictest:latest",
        "",
        "FAILED:",
        "  ✗ cnf-tests:4.8",
        "=========================================="
    ]
}

TASK [container_image_mirror : Fail if any images failed to mirror]
fatal: [bastion]: FAILED! => {
    "msg": "1 image(s) failed to mirror. See summary above for details."
}
```

## Use Cases

### Telco RAN Test Image Mirroring
Mirror test images from quay.io to bastion registries for spoke cluster testing:
```yaml
container_image_mirror_images:
  - {source: "quay.io/telcov10n-ci/oslat:latest", dest: "ran-test/oslat:latest"}
  - {source: "quay.io/telcov10n-ci/cyclictest:latest", dest: "ran-test/cyclictest:latest"}
  - {source: "quay.io/telcov10n-ci/stress-ng:latest", dest: "ran-test/stress-ng:latest"}
```

### Disconnected Environment Preparation
Mirror images to internal registry before deploying in air-gapped environment:
```yaml
container_image_mirror_operation: mirror
container_image_mirror_registry_host: registry.internal.corp
container_image_mirror_images:
  - {source: "quay.io/app/image:v1", dest: "production/app:v1"}
```

### Registry Cleanup
Remove old or deprecated images from internal registry:
```yaml
container_image_mirror_operation: remove
container_image_mirror_images:
  - {dest: "deprecated/old-app:v1"}
  - {dest: "test/temp-image:latest"}
```

## Notes

- **Continues on error**: The role continues mirroring all images even if some fail, then reports detailed results at the end
- **Pull secrets**: The role cleans up pull secrets after use for security
- **TLS verification**: Disabled by default for internal registries with self-signed certificates
- **Idempotency**: Checks for existing images before mirroring (though still attempts to mirror for freshness)
- **Namespace handling**: The `container_image_mirror_registry_namespace` is prepended to all destination images

## Troubleshooting

### Skopeo authentication errors
Ensure `container_image_mirror_pull_secret_string` contains valid credentials:
```bash
cat ~/.docker/config.json | base64 -w0
```

### TLS verification errors
If using self-signed certificates, ensure `container_image_mirror_dest_tls_verify: false`

### Permission errors during removal
Ensure the ansible user has sudo access to the registry storage path

### Image not found errors
Verify source image exists and is accessible:
```bash
skopeo inspect docker://quay.io/org/image:tag
```

## License
Apache-2.0

## Author Information
Telco Verification Team - Red Hat
