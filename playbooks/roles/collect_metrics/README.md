# Collect Metrics Ansible Role

## Disclaimer
This role is provided as-is, without any guarantees of support or maintenance.
The author or contributors are not responsible for any issues arising from the use of this role. Use it at your own discretion.

## Overview
The `collect_metrics` role collects operator versions, cluster metadata, and optional container image digests from OpenShift hub and/or spoke clusters. It writes a semicolon-delimited metrics string to a file for use by the upload-report playbook.

The role is designed to be modular — each metric category is an independent task file that can be included or excluded via the `collect_metrics_list` variable. Hub and spoke OCP metadata share a common implementation (`_cluster_general_ocp.yml`) configured by thin wrapper tasks. If a single metric fails to collect, the role continues and sets that metric to `N/A` (worker kernel collection is skipped on failure without `N/A` entries).

Container image digests are collected separately via `collect_containers_list` and are not selected through `collect_metrics_list`.

## Requirements
- Ansible 2.9+
- `kubernetes.core` collection installed
- `containers.podman` collection installed (when using `collect_containers_list`)
- Valid kubeconfig file(s) for the target cluster(s)
- Images referenced in `collect_containers_list` must be pullable on the Ansible target host (typically the bastion) for digest lookup via `podman_image_info`

## Role Variables

### Required

| Variable | Description |
|---|---|
| `collect_metrics_ci_lane` | CI lane identifier for the test run |
| `collect_metrics_list` | List of metric categories to collect (see below) |
| `collect_metrics_output_file` | Path to the output file |

### Conditionally required

| Variable | When required |
|---|---|
| `collect_metrics_spoke_kubeconfig` | Spoke-scoped categories in `collect_metrics_list` (`spoke_general_ocp`, `sriov`, `sriov_fec`, `ptp`, `logging`), or after `general_ocp` sets it for operator tasks |
| `collect_metrics_hub_kubeconfig` | Hub-scoped categories in `collect_metrics_list` (`hub_general_ocp`, `acm`, `talm`, `gitops`, `local_storage`) |
| `collect_metrics_kubeconfig` | When `general_ocp` is in `collect_metrics_list` (single-cluster collection) |

### Optional

| Variable | Default | Description |
|---|---|---|
| `collect_containers_list` | `[]` | List of container image references (e.g. `registry.example.com/org/image:tag`). Each image yields a metric keyed by the image name with `:` replaced by `_` |

### Output

The role sets the `collect_metrics_attributes` fact containing the full semicolon-delimited metrics string, which can be used in subsequent tasks. The metrics file is also written to `collect_metrics_output_file` and fetched to the Ansible controller (`flat: true`).

Example metric keys:

- `spoke_ocp_build`, `spoke_ocp_version`, `spoke_cluster_name`, `spoke_<node>_kernel_version`
- `hub_ocp_build`, `hub_ocp_version`, `hub_cluster_name`
- `ocp_build`, `ocp_version`, `cluster_name` (with `general_ocp`, no prefix)
- `sriov_operator`, `ptp_operator`, `acm_operator`, etc.
- `<image_name_with_underscores>` for container digests (digest value without `sha256:` prefix)
- `ci_lane`

## Metric Categories

| Category | Cluster | Description |
|---|---|---|
| `general_ocp` | single | OCP version, build, cluster name, and kernel version per worker node using `collect_metrics_kubeconfig`; also sets `collect_metrics_spoke_kubeconfig` for subsequent spoke operator tasks |
| `spoke_general_ocp` | spoke | Spoke OCP version, build, cluster name, and kernel version per worker node |
| `hub_general_ocp` | hub | Hub OCP version, build, and cluster name (no worker kernels) |
| `sriov` | spoke | SR-IOV operator version |
| `sriov_fec` | spoke | SR-IOV FEC operator version |
| `ptp` | spoke | PTP operator version |
| `acm` | hub | ACM operator version |
| `talm` | hub | TALM operator version |
| `gitops` | hub | GitOps operator version |
| `local_storage` | hub | Local Storage operator version |
| `logging` | spoke | Cluster Logging operator version |

## Usage

### Hub + Spoke (RAN-style, all metrics)

See `playbooks/ran/collect-metrics.yml` for hub-managed spoke kubeconfig discovery and default container images.

```yaml
- hosts: bastion
  gather_facts: false
  roles:
    - role: collect_metrics
      collect_metrics_spoke_kubeconfig: "{{ ran_spoke_kubeconfig }}"
      collect_metrics_hub_kubeconfig: "{{ ran_hub_kubeconfig }}"
      collect_metrics_ci_lane: "{{ ran_ci_lane }}"
      collect_metrics_output_file: /tmp/metrics/ran-metrics.txt
      collect_metrics_list:
        - spoke_general_ocp
        - hub_general_ocp
        - sriov
        - sriov_fec
        - ptp
        - acm
        - talm
        - gitops
        - local_storage
        - logging
      collect_containers_list:
        - registry.example.com:5000/ztp/ztp-site-generator:v4.17
        - quay.io/example/talm-fbc-4-17:latest
```

### Single cluster (`general_ocp`)

Use when only one kubeconfig is available. Operator metrics that target the spoke still use `collect_metrics_spoke_kubeconfig`, which `general_ocp` sets from `collect_metrics_kubeconfig`.

```yaml
- hosts: bastion
  gather_facts: false
  roles:
    - role: collect_metrics
      collect_metrics_kubeconfig: /path/to/kubeconfig
      collect_metrics_ci_lane: my-lane
      collect_metrics_output_file: /tmp/metrics/metrics.txt
      collect_metrics_list:
        - general_ocp
        - sriov
        - ptp
        - logging
```

### Spoke-only (explicit spoke kubeconfig)

```yaml
- hosts: bastion
  gather_facts: false
  roles:
    - role: collect_metrics
      collect_metrics_spoke_kubeconfig: /path/to/kubeconfig
      collect_metrics_ci_lane: my-lane
      collect_metrics_output_file: /tmp/metrics/metrics.txt
      collect_metrics_list:
        - spoke_general_ocp
        - sriov
        - ptp
        - logging
```

## Error Handling

Each metric category is wrapped in an Ansible `block/rescue`. If collection fails (e.g., operator not installed, API unreachable), the role:

1. Logs a debug message
2. Sets the metric value to `N/A` (where applicable)
3. Continues to the next metric

Worker kernel collection on failure only logs and skips; it does not append `N/A` per node.

The role will **not** fail due to a single metric collection error.

## Role Structure

```
collect_metrics/
├── tasks/
│   ├── main.yml                  # Orchestrator: validation, includes, output
│   ├── _cluster_general_ocp.yml  # Shared OCP version, cluster name, worker kernels
│   ├── general_ocp.yml           # Single-cluster wrapper for _cluster_general_ocp
│   ├── spoke_general_ocp.yml     # Spoke wrapper for _cluster_general_ocp
│   ├── hub_general_ocp.yml       # Hub wrapper for _cluster_general_ocp
│   ├── containers_digests.yml    # Podman image digest per collect_containers_list entry
│   ├── sriov.yml                 # SR-IOV operator version
│   ├── sriov_fec.yml             # SR-IOV FEC operator version
│   ├── ptp.yml                   # PTP operator version
│   ├── acm.yml                   # ACM operator version
│   ├── talm.yml                  # TALM operator version
│   ├── gitops.yml                # GitOps operator version
│   ├── local_storage.yml         # Local Storage operator version
│   └── logging.yml               # Cluster Logging operator version
└── README.md
```

## Dependencies

- `kubernetes.core` collection
- `containers.podman` collection (container digest collection only)

## License

Apache

## Author Information

This role was created by the Telco Verification CI Team.
