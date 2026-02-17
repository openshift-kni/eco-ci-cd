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
- Run `oc-mirror` to mirror operator catalogs/packages from PROD catalog
- Run `skopeo copy` to mirror operators from ART catalog
- Apply generated CatalogSource and IDMS manifests
- Mirror the `operator-registry` image referenced by the cluster payload

## Supported operator sources
- Production catalogs: Red Hat, certified, community
- ART image mirroring selected from FBC bundles

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
- Ansible collections:
  - `kubernetes.core`
  - `containers.podman`

## Role Variables
Key variables (see `defaults/main.yaml` for full list and defaults):
- `ocp_operator_mirror_registry_url`: Internal registry host:port
- `ocp_operator_mirror_registry_service_name`: Registry systemd unit (default: container-registry)
- `ocp_operator_mirror_folder`: Target repo namespace for operators (default: operators)
- `ocp_operator_mirror_disable_default_sources`: Disable default OperatorHub (bool, default: true)
- `ocp_operator_mirror_prod_catalog_sources`: Catalogs to mirror
- `ocp_operator_mirror_prod_default_channel_map`: Default channel per catalog. **Required** when mirroring operators with a specific channel that is not the default channel for that operator. This mapping allows the role to correctly identify and mirror non-default channels.
- `ocp_operator_mirror_pull_secret_path`: Path to auth.json (default: /tmp/auth.json)
- `ocp_operator_mirror_image_set_configuration_path`: Path to ImageSetConfiguration.yaml
- `ocp_operator_mirror_workspace_path`: oc-mirror workspace root
- `ocp_operator_mirror_kubeconfig`: Path to kubeconfig used by oc/k8s modules (optional). If empty, uses environment or module defaults.
- `ocp_operator_mirror_fbc_extract_dir`: Local directory used to extract FBC (IIB) catalog files (e.g., catalog.yaml) from index images during Konflux/IIB workflows. Default: `/tmp/fbc/`
- `ocp_operator_mirror_fbc_image_base`: Base repository for FBC (IIB) index images.
- `ocp_operator_mirror_art_images_share`: Registry/repo prefix used to pull ART images by digest when mapping source digests to a shared location.
- `ocp_operator_mirror_bundle_version`: Optional bundle version substring used to filter channel entries when selecting a bundle from FBC catalogs (e.g., `4.19.3`). Leave empty to select the latest entry.

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

**Note on `default_channel`**: When mirroring an operator with a specific channel that is not the default channel for that operator, you must configure `ocp_operator_mirror_prod_default_channel_map` to map the catalog to its default channel. This ensures the role can correctly identify and mirror the non-default channel you specified.

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

IIB (FBC) example with ART mirroring:
```yaml
- hosts: bastion
  gather_facts: yes
  roles:
    - role: ocp_operator_mirror
      vars:
        ocp_operator_mirror_registry_url: registry.local:9000
        ocp_operator_mirror_kubeconfig: /root/.kube/config
        ocp_operator_mirror_registry_user: "registry_user"
        ocp_operator_mirror_registry_password: "registry_password"
        ocp_operator_mirror_version: "4.19"
        ocp_operator_mirror_pull_secret: "pull-secret"
        ocp_operator_mirror_registry_url: disconnected.registry.local:5000
        ocp_operator_mirror_operators:
          - name: sriov-network-operator
            catalog: redhat-operators-sriov-art
            fbc_iib_repo: ose-sriov-network-rhel9-operator
            nsname: openshift-sriov-network-operator
            deploy_default_config: true
            channel: stable
          - name: ptp-operator
            catalog: redhat-operators-ptp-art
            nsname: openshift-ptp
            channel: stable
            fbc_iib_repo: ose-ptp-rhel9-operator
            ns_labels:
              workload.openshift.io/allowed: management
              name: openshift-ptp
```
## Typical flow executed by the role:
1. Verify required variables and optionally disable default OperatorHub sources
2. Reset local registry storage
3. Configure registry authentication and write auth.json
4. Mirror `operator-registry` image from payload and apply IDMS for ART repo
5. Build ImageSetConfiguration from selected operators
6. Run `oc-mirror/skopeo copy` and apply generated CatalogSource and IDMS manifests

## Outputs
- Applies CatalogSource and ImageDigestMirrorSet to the cluster
- Writes ImageSetConfiguration to `ocp_operator_mirror_image_set_configuration_path`
- Populates `ocp_operators_mirror_disconnected_config` with filtered operators

## Dependencies
None.

## License
Apache

## Author Information
This role was created by Nikita Kononov.

