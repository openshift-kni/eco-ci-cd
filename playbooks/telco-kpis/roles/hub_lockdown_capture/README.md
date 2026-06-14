# Hub Lockdown Capture Role

## Purpose

This role captures a complete snapshot of installed hub operators for reproducible deployments. It extracts operator CSVs, catalog digests, OCP version, and deployment metadata to create a lockdown JSON file.

## What It Captures

- **OCP Version**: Pull spec and version components from ClusterVersion
- **Catalog Sources**: CatalogSource images with SHA256 digests for immutability
- **Operator Subscriptions**: Installed CSVs, channels, namespaces, and subscription names
- **Operator Groups**: OperatorGroup names and target namespaces
- **FBC Upstream Sources**: For FBC operators (TALM), resolves and captures the upstream image digest for reproducible mirroring
- **Metadata**: Cluster name, capture timestamp, Jenkins build info

## Requirements

- Hub cluster kubeconfig with read access to:
  - `config.openshift.io/v1/ClusterVersion`
  - `operators.coreos.com/v1alpha1/CatalogSource` (openshift-marketplace namespace)
  - `operators.coreos.com/v1alpha1/Subscription` (all namespaces)
  - `operators.coreos.com/v1/OperatorGroup` (all namespaces)
- Ansible collections:
  - `kubernetes.core` (>= 2.4.2)

## Role Variables

### Required Variables

```yaml
cluster_kubeconfig: /path/to/kubeconfig  # Hub cluster kubeconfig
cluster_name: dev-kpi-01                 # Hub cluster name
cluster_ocp_version: "4.17"              # OCP version (major.minor)
output_file: /tmp/hub-lockdown.json      # Output JSON file path
```

### Optional Variables

```yaml
build_number: "123"                      # Jenkins build number (default: "")
job_name: "install-hub-operators"        # Jenkins job name (default: "")
```

## Usage

### In a Playbook

```yaml
- name: Capture Hub Lockdown State
  hosts: bastion
  tasks:
    - name: Include hub lockdown capture role
      ansible.builtin.include_role:
        name: telco-kpis/roles/hub_lockdown_capture
      vars:
        cluster_kubeconfig: /home/telcov10n/project/generated/dev-kpi-01/auth/kubeconfig
        cluster_name: dev-kpi-01
        cluster_ocp_version: "4.17"
        output_file: /tmp/hub-lockdown-dev-kpi-01.json
        build_number: "{{ lookup('env', 'BUILD_NUMBER') }}"
        job_name: "{{ lookup('env', 'JOB_NAME') }}"
```

### Standalone Playbook

See `playbooks/telco-kpis/capture-hub-lockdown.yml` for a complete example.

## FBC Upstream Source Capture (Reproducibility)

For File-Based Catalog (FBC) operators like TALM (Topology Aware Lifecycle Manager), the role captures the **upstream source digest** to enable fully reproducible deployments:

1. **Constructs upstream reference**: Based on OCP version, builds the upstream FBC image reference
   ```
   quay.io/redhat-user-workloads/telco-5g-tenant/topology-aware-lifecycle-manager-fbc-4-21:latest
   ```

2. **Resolves digest**: Uses `skopeo inspect` to get the actual SHA256 digest from the upstream registry
   ```
   sha256:abc123...
   ```

3. **Stores in lockdown**: Saves the full reference with digest as `fbc_upstream_source`
   ```
   quay.io/redhat-user-workloads/telco-5g-tenant/topology-aware-lifecycle-manager-fbc-4-21@sha256:abc123...
   ```

4. **Enables reproducibility**: When replaying the lockdown, this exact digest is used for mirroring, ensuring the same TALM version is deployed even months later

**Note**: Requires network access to upstream registry (quay.io) during capture.

## Output Format

The role generates a JSON file with the following structure:

```json
{
  "hub": {
    "ocp": {
      "pull_spec": "quay.io/openshift-release-dev/ocp-release@sha256:...",
      "major_version": "4",
      "minor_version": "21",
      "full_version": "4.21.3"
    },
    "operators": [
      {
        "name": "advanced-cluster-management",
        "namespace": "open-cluster-management",
        "catalog": "redhat-operators",
        "channel": "release-2.15",
        "subscription_name": "acm-operator-subscription",
        "starting_csv": "advanced-cluster-management.v2.15.1",
        "installed_csv": "advanced-cluster-management.v2.15.1",
        "install_plan_approval": "Automatic",
        "og_name": "open-cluster-management",
        "og_spec": {"targetNamespaces": ["open-cluster-management"]}
      },
      {
        "name": "topology-aware-lifecycle-manager",
        "namespace": "openshift-operators",
        "catalog": "topology-aware-lifecycle-manager-fbc",
        "channel": "stable",
        "subscription_name": "topology-aware-lifecycle-manager",
        "starting_csv": "topology-aware-lifecycle-manager.v4.21.0",
        "installed_csv": "topology-aware-lifecycle-manager.v4.21.0",
        "install_plan_approval": "Automatic",
        "og_name": "global-operators",
        "og_spec": {},
        "fbc_iib_repo": "latest",
        "fbc_upstream_source": "quay.io/redhat-user-workloads/telco-5g-tenant/topology-aware-lifecycle-manager-fbc-4-21@sha256:abc123..."
      }
    ],
    "catalog_sources": [
      {
        "name": "redhat-operators",
        "image": "registry.redhat.io/redhat/redhat-operator-index:v4.17",
        "digest": "sha256:abcd1234...",
        "full_reference": "registry.redhat.io/redhat/redhat-operator-index@sha256:abcd1234..."
      }
    ],
    "metadata": {
      "cluster_name": "dev-kpi-01",
      "capture_timestamp": "2026-06-09T10:30:00Z",
      "build_number": "123",
      "job_name": "telco-kpis-install-hub-operators"
    }
  }
}
```

## Integration with Jenkins

This role is integrated into the `telco-kpis-install-hub-operators` Jenkins job:

1. **Parameter**: `GENERATE_HUB_LOCKDOWN` (boolean) - Enable lockdown generation
2. **Stage**: "Generate Hub Lockdown" runs after operator installation
3. **Artifact**: Saved as `hub-lockdown-{HUB}-build-number-{BUILD_NUMBER}.json`
4. **Comparison**: If `HUB_LOCKDOWN_URI` also provided, compares generated vs input lockdown

### Jenkins Workflow

```groovy
stage('Generate Hub Lockdown') {
    when {
        expression { params.GENERATE_HUB_LOCKDOWN }
    }
    steps {
        script {
            def lockdownFilename = "hub-lockdown-${params.HUB}-build-number-${BUILD_NUMBER}.json"
            runAnsiblePlaybook(
                playbookName: "telco-kpis/capture-hub-lockdown.yml",
                extraVars: [
                    "kubeconfig=${KUBECONFIG_PATH}",
                    "hub_cluster=${params.HUB}",
                    "ocp_version=${params.OCP_VERSION}",
                    "lockdown_output_file=/tmp/${lockdownFilename}",
                    "jenkins_build_number=${BUILD_NUMBER}",
                    "jenkins_job_name=${JOB_NAME}"
                ]
            )
            archiveArtifacts artifacts: "**/${lockdownFilename}", fingerprint: true
        }
    }
}
```

## Reproducible Deployments

### Capture Process

1. Install operators on hub cluster (initial deployment)
2. Enable `GENERATE_HUB_LOCKDOWN` parameter
3. Role captures exact operator state (CSVs, channels, catalog digests)
4. Lockdown JSON saved as Jenkins artifact

### Replay Process

1. Download lockdown JSON from previous build artifact
2. Set `HUB_LOCKDOWN_URI` parameter to lockdown JSON URL
3. Operators installed with exact CSVs and catalog digests from lockdown
4. Result: Identical operator configuration as captured cluster

## Related Roles

- **`lockdown_hub_config`**: Parses lockdown JSON and sets deployment variables
- **`ocp_operator_deployment`**: Deploys operators using lockdown configuration

## Related Playbooks

- **`capture-hub-lockdown.yml`**: Orchestrates lockdown capture
- **`compare-hub-lockdown.yml`**: Compares generated vs input lockdown (validation)

## Files

```
playbooks/telco-kpis/roles/hub_lockdown_capture/
├── README.md
├── tasks/
│   └── main.yml                 # Main task list
└── templates/
    └── hub-lockdown.json.j2     # Output JSON template
```

## Testing

```bash
# Capture lockdown from dev-kpi-01
ansible-playbook playbooks/telco-kpis/capture-hub-lockdown.yml \
  -i inventories/ocp-deployment/build-inventory.py \
  --extra-vars "hub_cluster=dev-kpi-01 ocp_version=4.17 kubeconfig=/path/to/kubeconfig"

# Verify output
jq . /tmp/hub-lockdown-dev-kpi-01-*.json

# Deploy from lockdown (replay)
ansible-playbook playbooks/deploy-ocp-operators.yml \
  -i inventories/ocp-deployment/build-inventory.py \
  --extra-vars "kubeconfig=/path/to/kubeconfig version=4.17 hub_lockdown_uri=https://example.com/hub-lockdown.json"
```

## Known Limitations

- Only captures hub operators (not spoke operators)
- Requires CatalogSource images to include SHA256 digests
- Does not capture operator custom resources (CR) configurations
- Assumes OperatorGroup exists in same namespace as Subscription
- FBC upstream source resolution requires network access to quay.io during capture
- If upstream registry is unreachable during capture, `fbc_upstream_source` won't be set (falls back to `fbc_iib_repo: "latest"` which may not be fully reproducible)

## Future Enhancements

- Spoke operator lockdown support (similar pattern for spoke clusters)
- Custom resource (CR) snapshot and restore
- Automatic CR drift detection between lockdown and current state
