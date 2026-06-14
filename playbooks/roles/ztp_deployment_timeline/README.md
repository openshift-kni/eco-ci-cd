# ztp_deployment_timeline

Ansible role to collect Zero Touch Provisioning (ZTP) deployment timeline data from OpenShift hub clusters using Advanced Cluster Management (ACM).

## Description

This role queries ACM/ZTP resources on a hub cluster to build a complete deployment timeline from ClusterInstance creation to TALM ClusterGroupUpgrade completion. It provides detailed insights into every phase of the deployment process, including GitOps sync, installation, discovery, provisioning, import, and policy application.

The role sets facts with deployment timeline information that can be used by test playbooks or other automation to validate deployment performance, generate reports, or troubleshoot failed deployments.

## Requirements

- Hub cluster with ACM/ZTP deployed
- `kubernetes.core` collection installed
- Valid kubeconfig for hub cluster access
- Spoke cluster deployed via ZTP (AgentClusterInstall or ImageBasedInstall)

## Role Variables

### Required Variables

- `spoke_cluster`: Name of the spoke cluster (ManagedCluster name)
- `hub_kubeconfig`: Path to hub cluster kubeconfig file on the bastion

### Optional Variables

None. The role automatically detects deployment method (AI vs IBI) and available resources.

## Facts Set by Role

After execution, the role sets the following facts:

### Timeline Facts

- `ztp_deployment_timeline_start_time`: ISO 8601 timestamp of deployment start (ClusterInstance creation)
- `ztp_deployment_timeline_end_time`: ISO 8601 timestamp of deployment completion (TALM CGU completion)
- `ztp_deployment_timeline_duration_seconds`: Total deployment time in seconds
- `ztp_deployment_timeline_duration_formatted`: Human-readable duration (e.g., "1h21m01s")

### Event Data

- `ztp_deployment_timeline_events`: List of timeline events, each containing:
  - `timestamp`: ISO 8601 timestamp
  - `event`: Event type identifier
  - `event_description`: Human-readable event description
  - `milestone`: Deployment phase (0-GITOPS_APPLICATION, 1-GITOPS_SYNC, etc.)

### Status Facts

- `ztp_deployment_timeline_success`: Boolean indicating if timeline data was successfully collected
- `ztp_deployment_timeline_error`: Error message if collection failed
- `ztp_deployment_timeline_deployment_method`: "AI" (Assisted Installer) or "IBI" (Image-based Install)

### Milestone Timestamps

- `ztp_deployment_timeline_clusterinstance_created`: ClusterInstance creation timestamp
- `ztp_deployment_timeline_gitops_sync`: ManagedCluster creation timestamp
- `ztp_deployment_timeline_cluster_install_created`: AgentClusterInstall/ImageBasedInstall creation timestamp
- `ztp_deployment_timeline_iso_ready`: Discovery ISO ready timestamp (AI only)
- `ztp_deployment_timeline_agent_registered`: Agent registration timestamp (AI only)
- `ztp_deployment_timeline_installation_started`: Installation start timestamp
- `ztp_deployment_timeline_installation_completed`: Installation completion timestamp
- `ztp_deployment_timeline_cluster_available`: Cluster available in ACM timestamp
- `ztp_deployment_timeline_talm_cgu_completed`: TALM CGU completion timestamp

## Example Playbook

### Basic Usage

```yaml
---
- name: Collect ZTP deployment timeline
  hosts: bastion
  gather_facts: false
  
  tasks:
    - name: Collect deployment timeline for spoke cluster
      ansible.builtin.include_role:
        name: ztp_deployment_timeline
      vars:
        spoke_cluster: "spree-02"
        hub_kubeconfig: "/home/telcov10n/project/generated/kni-qe-71/auth/kubeconfig"
    
    - name: Display timeline summary
      ansible.builtin.debug:
        msg:
          - "Deployment Method: {{ ztp_deployment_timeline_deployment_method }}"
          - "Start Time: {{ ztp_deployment_timeline_start_time }}"
          - "End Time: {{ ztp_deployment_timeline_end_time }}"
          - "Duration: {{ ztp_deployment_timeline_duration_formatted }}"
          - "Total Events: {{ ztp_deployment_timeline_events | length }}"
```

### Deployment Time Validation

```yaml
---
- name: Validate ZTP deployment time
  hosts: bastion
  gather_facts: false
  
  vars:
    threshold_duration: "2h0m"  # 120 minutes for AI deployments
  
  tasks:
    - name: Collect deployment timeline
      ansible.builtin.include_role:
        name: ztp_deployment_timeline
      vars:
        spoke_cluster: "{{ SPOKE_CLUSTER }}"
        hub_kubeconfig: "{{ HUB_KUBECONFIG }}"
    
    - name: Parse threshold duration
      ansible.builtin.set_fact:
        threshold_seconds: "{{ (threshold_duration | regex_search('(\\d+)h') | default('0h') | regex_replace('h', '') | int * 3600) + (threshold_duration | regex_search('(\\d+)m') | default('0m') | regex_replace('m', '') | int * 60) }}"
    
    - name: Validate deployment time
      ansible.builtin.assert:
        that:
          - ztp_deployment_timeline_success | bool
          - ztp_deployment_timeline_duration_seconds <= (threshold_seconds | int)
        fail_msg: |
          Deployment time exceeded threshold!
          Actual: {{ ztp_deployment_timeline_duration_formatted }} ({{ ztp_deployment_timeline_duration_seconds }}s)
          Threshold: {{ threshold_duration }} ({{ threshold_seconds }}s)
        success_msg: |
          Deployment completed within threshold
          Actual: {{ ztp_deployment_timeline_duration_formatted }} ({{ ztp_deployment_timeline_duration_seconds }}s)
          Threshold: {{ threshold_duration }} ({{ threshold_seconds }}s)
```

### Generate Timeline Report

```yaml
---
- name: Generate deployment timeline report
  hosts: bastion
  gather_facts: false
  
  tasks:
    - name: Collect deployment timeline
      ansible.builtin.include_role:
        name: ztp_deployment_timeline
      vars:
        spoke_cluster: "{{ SPOKE_CLUSTER }}"
        hub_kubeconfig: "{{ HUB_KUBECONFIG }}"
    
    - name: Generate JSON timeline
      ansible.builtin.copy:
        content: "{{ ztp_deployment_timeline_events | to_nice_json }}"
        dest: "/tmp/{{ spoke_cluster }}-timeline.json"
    
    - name: Generate summary report
      ansible.builtin.template:
        src: timeline-summary.j2
        dest: "/tmp/{{ spoke_cluster }}-timeline-summary.txt"
```

## Deployment Methods Supported

### Assisted Installer (AI)

Traditional ZTP deployment using AgentClusterInstall:
- Discovery ISO generation
- Agent registration and binding
- Assisted Service installation
- Typical duration: 60-120 minutes

Measurement: `ClusterInstance.metadata.creationTimestamp` → `ClusterGroupUpgrade.status.status.completedAt`

### Image-Based Install (IBI)

Fast deployment using pre-built images with ImageBasedInstall:
- Pre-configured cluster image
- Direct installation without discovery phase
- Typical duration: 15-30 minutes

Measurement: `ClusterInstance.metadata.creationTimestamp` → `ClusterGroupUpgrade.status.status.completedAt`

## Timeline Phases

The role categorizes events into deployment milestones:

- **0-GITOPS_APPLICATION**: ClusterInstance creation (SiteConfig v2 operator)
- **1-GITOPS_SYNC**: ManagedCluster creation
- **2-CLUSTER_INSTALL**: OpenShift installation process
- **3-DISCOVERY**: ISO creation, agent registration (AI only)
- **4-PROVISIONING**: BareMetalHost hardware provisioning
- **6-IMPORT**: Initial ACM import
- **7-MANIFESTWORK**: ACM addon deployments
- **8-POLICY**: Policy application and compliance
- **9-TALM_CGU_COMPLETION**: TALM recognizes all policies compliant
- **10-ZTP_DONE**: ztp-done label present

## Error Handling

If timeline collection fails, the role sets:
- `ztp_deployment_timeline_success: false`
- `ztp_deployment_timeline_error`: Error message describing the failure

Common failure scenarios:
- Hub cluster not accessible
- Spoke cluster not found
- Missing ClusterInstance resource (not a ZTP deployment)
- Missing TALM ClusterGroupUpgrade (policies not applied)

## Dependencies

- `kubernetes.core` collection (for k8s_info module)

## License

Apache License 2.0

## Author Information

Red Hat Telco Verification Team
