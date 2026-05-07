# lockdown_hub_config Role

## Purpose

Parses hub lockdown JSON and sets hub deployment configuration facts for Telco-KPIs testing reproducibility.

## Description

This role downloads and parses hub lockdown JSON to extract exact hub platform component versions:
- Hub OCP release image (`hub.ocp.pull_spec`)
- Hub OCP version (`hub.ocp.major_version`, `hub.ocp.minor_version`)
- ACM/MCE configuration (`hub.acm.*`)
- TALM operator catalog index (`hub.talm.pull_spec`)
- GitOps operator catalog index (`hub.gitops.pull_spec`)

The role is designed to integrate with the parametrized hub lockdown approach, allowing optional lockdown enforcement without breaking existing workflows.

## Requirements

- `jq` package installed on bastion (for JSON validation)
- Access to hub lockdown JSON file (via HTTP/HTTPS URL)

## Role Variables

### Input Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `hub_lockdown_uri` | No | `""` | URL to hub lockdown JSON file |

### Output Facts

When `hub_lockdown_uri` is provided, the role sets the following facts:

| Fact | Description | Example |
|------|-------------|---------|
| `use_hub_lockdown` | Whether hub lockdown is enabled | `true` |
| `hub_ocp_pull_spec` | Exact hub OCP release image | `quay.io/openshift-release-dev/ocp-release:4.20.4-x86_64` |
| `hub_ocp_major_version` | Hub OCP major version | `4` |
| `hub_ocp_minor_version` | Hub OCP minor version | `20` |
| `hub_acm_config` | ACM configuration dict | `{"version_override": "2.15", "acm_override": "v2.15.0", ...}` |
| `hub_talm_pull_spec` | TALM operator catalog index | `registry.redhat.io/redhat/redhat-operator-index:v4.20` |
| `hub_gitops_pull_spec` | GitOps operator catalog index | `registry.redhat.io/redhat/redhat-operator-index:v4.20` |

## Dependencies

None

## Example Playbook

### Basic Usage (Hub OCP Deployment)

```yaml
---
- name: Deploy hub with optional lockdown
  hosts: bastion
  tasks:
    # Parse hub lockdown if provided
    - name: Parse hub lockdown JSON
      ansible.builtin.include_role:
        name: lockdown_hub_config
      vars:
        hub_lockdown_uri: "{{ lookup('env', 'HUB_LOCKDOWN_URI') | default('', true) }}"
      when: lookup('env', 'HUB_LOCKDOWN_URI') | length > 0

    # Override release variable if hub lockdown is active
    - name: Set OCP release from hub lockdown
      ansible.builtin.set_fact:
        release: "{{ hub_ocp_pull_spec }}"
      when: use_hub_lockdown | default(false)

    # Rest of deployment playbook...
```

### With Hub Operators

```yaml
---
- name: Install hub operators with lockdown
  hosts: bastion
  tasks:
    - name: Parse hub lockdown JSON
      ansible.builtin.include_role:
        name: lockdown_hub_config
      vars:
        hub_lockdown_uri: "{{ hub_lockdown_uri }}"
      when: hub_lockdown_uri is defined and hub_lockdown_uri | length > 0

    - name: Install ACM with lockdown config
      ansible.builtin.include_role:
        name: ocp_operator_deployment
      vars:
        operator_name: "advanced-cluster-management"
        acm_version_override: "{{ hub_acm_config.version_override | default('') }}"
        acm_catalog_override: "{{ hub_acm_config.acm_override | default('') }}"
      when: use_hub_lockdown | default(false)
```

## Hub Lockdown JSON Format

Example hub lockdown JSON structure:

```json
{
  "hub": {
    "ocp": {
      "major_version": "4",
      "minor_version": "20",
      "pull_spec": "quay.io/openshift-release-dev/ocp-release:4.20.4-x86_64"
    },
    "acm": {
      "version_override": "2.15",
      "acm_override": "v2.15.0",
      "mce_override": "v2.10.0",
      "iib_or_snapshot": "konflux"
    },
    "talm": {
      "pull_spec": "registry.redhat.io/redhat/redhat-operator-index:v4.20"
    },
    "gitops": {
      "pull_spec": "registry.redhat.io/redhat/redhat-operator-index:v4.20"
    }
  }
}
```

## Backward Compatibility

This role is **100% backward compatible**:
- If `hub_lockdown_uri` is empty or not provided → role skips processing
- Existing playbooks continue working without modification
- Hub lockdown is **opt-in** via parameter

## Error Handling

The role performs the following validations:
1. **Download validation**: Fails if hub lockdown JSON cannot be downloaded (with 3 retries)
2. **JSON structure validation**: Fails if `.hub.ocp` section is missing
3. **Graceful defaults**: Optional fields (TALM, GitOps) default to empty string if missing

## Testing

### Test with existing lockdown file

```bash
# Export hub lockdown URI
export HUB_LOCKDOWN_URI="https://gitlab.cee.redhat.com/ran/dev-kpi-pipeline/-/raw/main/lockdown-hub-x86_64.json"

# Run deploy-ocp-sno playbook
ansible-playbook playbooks/deploy-ocp-sno.yml \
  -i inventories/ocp-deployment/build-inventory.py \
  --extra-vars "cluster_name=kni-qe-71 release=4.21"

# Verify hub_ocp_pull_spec is used instead of release parameter
```

### Test without lockdown (backward compatibility)

```bash
# No HUB_LOCKDOWN_URI set
ansible-playbook playbooks/deploy-ocp-sno.yml \
  -i inventories/ocp-deployment/build-inventory.py \
  --extra-vars "cluster_name=kni-qe-71 release=4.21"

# Should use release=4.21 (current behavior)
```

## License

See repository LICENSE file.

## Author Information

Telco Verification CI/CD Team
