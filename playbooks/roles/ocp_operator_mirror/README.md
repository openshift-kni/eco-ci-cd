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
- Run `oc-mirror --v2 --remove-signatures=false` for each full ART/FBC catalog
- Optionally apply generated CatalogSource, IDMS, and ITMS resources
- Mirror the `operator-registry` image referenced by the cluster payload

## Supported operator sources
- Production catalogs: Red Hat, certified, community
- ART image mirroring selected from FBC bundles

## Features
- Derives catalog version (major.minor) from `ocp_operator_mirror_version` and maps production catalogs to index images (e.g. `redhat-operator-index:v4.19`, `certified-operator-index:v4.19`, `community-operator-index:v4.19`)
- **Per-operator catalog version override**: For production catalogs, any operator may set `catalog_version_override` to pin that catalog’s index to a different version (e.g. use certified-operators at v4.18 while the rest use 4.19)
- Supports Red Hat, certified, and community catalogs
- Selects each operator’s requested `channel`, falling back to `ocp_operator_mirror_prod_default_channel_map`, and sets it as the package `defaultChannel` and sole channel in the ImageSetConfiguration
- After mirroring, mutates production operator entries in place so `catalog` is set to the mirrored CatalogSource name (e.g. `cs-redhat-operator-index-v4-19`) for use by downstream deployment
- Idempotent mirroring with pre-checks and post-verify
- Secure handling of credentials (no_log on sensitive tasks)

## Requirements
- Ansible 2.9+
- Tools available on the bastion/runner:
  - `oc` (connected to the cluster)
  - `skopeo`
  - `oc-mirror` 4.20+ with v2 and signature mirroring support
  - `bash`
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
- `ocp_operator_mirror_skip_manifest_apply`: Skip applying generated CatalogSource, IDMS, and ITMS resources, including the operator-registry IDMS (bool, default: false). Mirroring and manifest generation still run.
- `ocp_operator_mirror_prod_catalog_sources`: Catalogs to mirror
- `ocp_operator_mirror_prod_default_channel_map`: Fallback channel per catalog, used when an operator omits `channel`.
- `ocp_operator_mirror_pull_secret_path`: Path to auth.json (default: /tmp/auth.json)
- `ocp_operator_mirror_image_set_configuration_path`: Path to ImageSetConfiguration.yaml
- `ocp_operator_mirror_workspace_path`: oc-mirror workspace root
- `ocp_operator_mirror_prod_catalog_image_name`: Production Red Hat operator index image (default: `registry.redhat.io/redhat/redhat-operator-index`). Tagged with `production_catalog_version` / `catalog_version`.
- `ocp_operator_mirror_kubeconfig`: Path to kubeconfig used by oc/k8s modules (optional). If empty, uses environment or module defaults.
- `ocp_operator_mirror_fbc_image_base`: Default base repository for FBC (IIB) index images.
- `ocp_operator_mirror_fbc_target_tag`: Tag used when publishing FBC catalogs to the internal registry (default: `latest`).

**FBC operator items:**
- `fbc_iib_repo`: Used to construct the catalog tag. The default tag is `ocp__<version>__<fbc_iib_repo>`; an item with `ocp_operator_mirror_fbc_image_base` or an ACM/MCE catalog uses `fbc_iib_repo` directly.
- `ocp_operator_mirror_fbc_image_base`: Optional per-item catalog repository override.
- `fbc_target_catalog`: Optional target repository path below `ocp_operator_mirror_folder`. Defaults to `fbc_iib_repo`, or to the item's `catalog` name for an explicit `fbc` source.
- `fbc_target_tag`: Optional per-item override for the published catalog tag.
- `fbc`: Optional complete source catalog reference, including a digest for pinned catalogs.
- `name` and `channel`: The package and channel to mirror. The channel is also set as the package's `defaultChannel`.

All FBC catalogs are mirrored in a single oc-mirror v2 run. Each catalog is filtered to the requested package and channel, including signatures. The generated
CatalogSource keeps the item's `catalog` name for downstream deployment. The requested target tag
is published at the destination. As a workaround for OCPBUGS-135380, when the target catalog
contains the target tag, oc-mirror uses a tag derived from the source digest and the role copies
that image to the requested tag. The generated CatalogSource references the digest-derived tag. For OCPBUGS-136180, a target
repository containing underscores is replaced in the ImageSetConfiguration with a deterministic
`fbc-<hash>` repository. The role copies the mirrored catalog to the original requested repository
and tag, while the generated CatalogSource continues to reference the temporary image. Both
workarounds can apply to the same catalog.
Generated
IDMS and ITMS resources use `-prod` or `-fbc` suffixes plus a short digest of the generated mapping. Repeated runs with
different hub or spoke mappings therefore coexist, while rerunning the same mapping remains idempotent.
During FBC mirroring, a temporary
`/etc/containers/registries.conf.d/ocp-operator-mirror-art.conf` routes production
references to `registry.stage.redhat.io`, following the legacy ART configuration.
An `always` block removes it on success or failure before other mirroring proceeds.
The runner needs privilege escalation for this file and credentials for stage.
Do not run other mirroring concurrently on this host while this override is active.

The former catalog extraction, image rewriting, shared ART image repository,
and manual signature copies are removed.
`bundle_version`, `multifile_catalog`, and `art_fbc` no longer select or
rewrite FBC content; pin the source catalog with `fbc` when needed.

The role pins the source catalog digest before mirroring. When
`ocp_operator_mirror_generate_lockdown` is enabled, it also records that pinned FBC reference
through the lockdown role. A provided `fbc` digest is used directly. FBC lockdown entries contain no `bundle` field; legacy
`bundle` pins are ignored.

**Operator item (production catalogs):**
- `catalog_version_override`: Optional. When set on an operator that uses a production catalog (redhat-operators, certified-operators, community-operators), that catalog’s index image version is overridden (e.g. `"4.18"`). Useful to pin one catalog to a different major.minor than `ocp_operator_mirror_version`.
- `channel`: Channel to mirror. Used as both the package `defaultChannel` and the sole entry in `channels`. If omitted, uses the catalog’s entry in `ocp_operator_mirror_prod_default_channel_map`.

Provide operator list as `ocp_operator_mirror_operators` (array of dicts). Operators whose `catalog` is in `ocp_operator_mirror_prod_catalog_sources` (redhat-operators, certified-operators, community-operators) are mirrored from production index images; the role then mutates their `catalog` to the mirrored CatalogSource name (e.g. `cs-redhat-operator-index-v4-19`) for downstream use.

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
  # Optional: pin this catalog's index to a different version (e.g. 4.18)
  - name: some-certified-operator
    catalog: certified-operators
    channel: stable
    catalog_version_override: "4.18"
```


**Note on `catalog_version_override`**: For production catalogs only. When set on an operator, that catalog’s index image version is overridden (e.g. `certified-operator-index:v4.18`). The first override seen per catalog type wins; use when you need one catalog at a different major.minor than `ocp_operator_mirror_version`.

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
4. Mirror `operator-registry` image from payload and optionally apply IDMS for ART repo
5. **Production catalogs**: Derive catalog version (major.minor), apply any per-operator `catalog_version_override`, map catalogs to index images; build package lists per catalog (redhat/certified/community) with the selected channel as each package’s `defaultChannel` and sole channel; assemble ImageSetConfiguration; run `oc-mirror`; optionally apply generated cluster resources; then mutate `ocp_operator_mirror_operators_prod` so each operator’s `catalog` is the mirrored CatalogSource name
6. **FBC/ART**: Mirror from IIB/FBC and apply manifests as configured
7. Merge production and FBC operator lists into `ocp_operators_mirror_disconnected_config`

## Outputs
- Optionally applies CatalogSource, ImageDigestMirrorSet, and ImageTagMirrorSet resources to the cluster
- Writes ImageSetConfiguration to `ocp_operator_mirror_image_set_configuration_path`
- Populates `ocp_operators_mirror_disconnected_config` with filtered operators

## Dependencies
None.

## License
Apache

## Author Information
This role was created by Nikita Kononov.

