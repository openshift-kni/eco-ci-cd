# Collect Metrics Ansible Role

## Disclaimer
This role is provided as-is, without any guarantees of support or maintenance.
The author or contributors are not responsible for any issues arising from the use of this role. Use it at your own discretion.

## Overview
The `collect_metrics` role collects operator versions and cluster metadata from OpenShift hub and/or spoke clusters. It writes a semicolon-delimited metrics string to a file for use by the upload-report playbook.

The role is designed to be modular — each metric category is an independent task file that can be included or excluded via the `collect_metrics_list` variable. If a single metric fails to collect, the role continues and sets that metric to `N/A`.

## Requirements
- Ansible 2.9+
- `kubernetes.core` collection installed
- Valid kubeconfig file(s) for the target cluster(s)

## Role Variables

All variables are **required** (no defaults):

| Variable | Description |
|---|---|
| `collect_metrics_spoke_kubeconfig` | Path to the spoke cluster kubeconfig file |
| `collect_metrics_hub_kubeconfig` | Path to the hub cluster kubeconfig file (required only when hub metrics are in `collect_metrics_list`) |
| `collect_metrics_ci_lane` | CI lane identifier for the test run |
| `collect_metrics_list` | List of metric categories to collect (see below) |
| `collect_metrics_output_file` | Path to the output file |

### Output

The role sets the `collect_metrics_attributes` fact containing the full semicolon-delimited metrics string, which can be used in subsequent tasks.

## Metric Categories

| Category | Cluster | Description |
|---|---|---|
| `spoke_general_ocp` | spoke | Spoke OCP version, build, and cluster name |
| `hub_general_ocp` | hub | Hub OCP version, build, and cluster name |
| `sriov` | spoke | SR-IOV operator version |
| `sriov_fec` | spoke | SR-IOV FEC operator version |
| `ptp` | spoke | PTP operator version |
| `acm` | hub | ACM operator version |
| `talm` | hub | TALM operator version |
| `gitops` | hub | GitOps operator version |
| `logging` | spoke | Cluster Logging operator version |

## Usage

### Hub + Spoke (all metrics)

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
        - logging
```

### Single cluster (spoke only)

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

Each metric is wrapped in an Ansible `block/rescue`. If a metric collection fails (e.g., operator not installed, API unreachable), the role:
1. Logs a warning
2. Sets the metric value to `N/A`
3. Continues to the next metric

The role will **not** fail due to a single metric collection error.

## Role Structure

```
collect_metrics/
├── meta/
│   └── main.yml
├── tasks/
│   ├── main.yml              # Orchestrator: validation, includes, output
│   ├── spoke_general_ocp.yml # Spoke OCP version + cluster name
│   ├── hub_general_ocp.yml   # Hub OCP version + cluster name
│   ├── sriov.yml             # SR-IOV operator version
│   ├── sriov_fec.yml         # SR-IOV FEC operator version
│   ├── ptp.yml               # PTP operator version
│   ├── acm.yml               # ACM operator version
│   ├── talm.yml              # TALM operator version
│   ├── gitops.yml            # GitOps operator version
│   └── logging.yml           # Cluster Logging operator version
└── README.md
```

## Dependencies

- `kubernetes.core` collection

## License

Apache

## Author Information

This role was created by the Telco Verification CI Team.
