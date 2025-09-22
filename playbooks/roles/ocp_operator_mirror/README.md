# OCP Operator Mirror Ansible Role

## Disclaimer
This role is provided as-is, without guarantees of support or maintenance.
Use at your own discretion.

## Overview
The `ocp_operator_mirror` role mirrors OpenShift operator content to an internal
registry for disconnected or partially connected environments. It can:
- Optionally disable default OperatorHub sources
- Prepare/clean the local registry storage
- Generate an ImageSetConfiguration from your operator list
- Run `oc-mirror` to mirror operator catalogs/packages
- Apply generated CatalogSource and IDMS manifests
- Mirror the `operator-registry` image referenced by the cluster payload

## Features
- Derives catalog version (major.minor) and maps catalogs to index images
- Supports Red Hat, certified, and community catalogs
- Selects operator channels per catalog with sensible defaults
- Idempotent mirroring with pre-checks and post-verify
- Secure handling of credentials (no_log on sensitive tasks)

## Requirements
- Ansible 2.9+
- Tools available on the bastion/runner:
  - `oc` (connected to the cluster)
  - `skopeo`
  - `oc-mirror`
- Reachable internal registry with credentials

## Role Variables
Key variables (see `defaults/main.yaml` for full list and defaults):
- `ocp_operator_mirror_registry_url`: Internal registry host:port
- `ocp_operator_mirror_registry_service_name`: Registry systemd unit (default: container-registry)
- `ocp_operator_mirror_folder`: Target repo namespace for operators (default: operators)
- `ocp_operator_mirror_disable_default_sources`: Disable default OperatorHub (bool, defualt: true)
- `ocp_operator_mirror_prod_catalog_sources`: Catalogs to mirror
- `ocp_operator_mirror_prod_default_channel_map`: Default channel per catalog
- `ocp_operator_mirror_pull_secret_path`: Path to auth.json (default: /tmp/auth.json)
- `ocp_operator_mirror_image_set_configuration_path`: Path to ImageSetConfiguration.yaml
- `ocp_operator_mirror_workspace_path`: oc-mirror workspace root
- `ocp_operator_mirror_kubeconfig`: Path to kubeconfig used by oc/k8s modules (optional). If empty, uses environment or module defaults.

Provide operator list as `ocp_operator_mirror_operators` (array of dicts):
```yaml
ocp_operator_mirror_operators:
  - name: local-storage-operator
    catalog: redhat-operators
    channel: stable
  - name: advanced-cluster-management
    catalog: redhat-operators
    channel: release-2.11
  - name: sriov-fec
    catalog: certified-operators
    nsname: vran-acceleration-operators
    channel: stable
```

## Usage
Minimal playbook example:
```yaml
- hosts: bastion
  gather_facts: yes
  roles:
    - role: ocp_operator_mirror
      vars:
        ocp_operator_mirror_registry_url: registry.local:9000
        ocp_operator_mirror_kubeconfig: "/root/.kube/config"
        ocp_operator_mirror_operators: "{{ operators }}"  # can be list or JSON string
```
Playbook example:
```yaml
- hosts: bastion
  gather_facts: yes
  roles:
    - role: ocp_operator_mirror
      vars:
        ocp_operator_mirror_registry_url: disconnected.registry.local:5000
         ocp_operator_mirror_kubeconfig: "/root/.kube/config"
        ocp_operator_mirror_registry_user: "registry_user"
        ocp_operator_mirror_registry_password: "registry_password"
        ocp_operator_mirror_pull_secret: "pull-secret"
        ocp_operator_mirror_version: "4.19"
        ocp_operator_mirror_operators: "{{ operators }}"
```
Typical flow executed by the role:
1. Verify required variables and optionally disable default OperatorHub sources
2. Reset local registry storage
3. Configure registry authentication and write auth.json
4. Mirror `operator-registry` image from payload and apply IDMS for ART repo
5. Build ImageSetConfiguration from selected operators
6. Run `oc-mirror` and apply generated CatalogSource and IDMS manifests

## Outputs
- Applies CatalogSource and ImageDigestMirrorSet to the cluster
- Writes ImageSetConfiguration to `ocp_operator_mirror_image_set_configuration_path`
- Populates `ocp_operators_mirror_disconnected_config` with filtered operators
```

## Dependencies
None.

## License
Apache

## Author Information
This role was created by Nikita Kononov.

