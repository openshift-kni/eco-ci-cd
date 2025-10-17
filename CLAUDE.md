# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is an Ansible automation framework for Telco Verification CI/CD pipelines. It provides end-to-end OpenShift cluster deployment, CNF (Cloud-Native Network Function) testing, and infrastructure management capabilities for OpenShift Edge computing deployments.

## Common Commands

### Install Dependencies
```bash
# Install Ansible collection dependencies
ansible-galaxy collection install -r requirements.yml
```

### Running Playbooks

**Deploy OpenShift Hybrid Multinode Cluster:**
```bash
# Deploy latest version of a specific minor release
ansible-playbook ./playbooks/deploy-ocp-hybrid-multinode.yml \
  -i ./inventories/ocp-deployment/build-inventory.py \
  --extra-vars 'release=4.17'

# Deploy specific version
ansible-playbook ./playbooks/deploy-ocp-hybrid-multinode.yml \
  -i ./inventories/ocp-deployment/build-inventory.py \
  --extra-vars 'release=4.17.9'

# Deploy with trusted internal registry (disconnected mode)
ansible-playbook ./playbooks/deploy-ocp-hybrid-multinode.yml \
  -i ./inventories/ocp-deployment/build-inventory.py \
  --extra-vars "release=4.17.9 internal_registry=true"
```

**Deploy OpenShift Operators:**
```bash
# Connected mode
ansible-playbook ./playbooks/deploy-ocp-operators.yml \
  -i ./inventories/ocp-deployment/build-inventory.py \
  --extra-vars 'kubeconfig="/path/to/kubeconfig" version="4.17" operators=[...]'

# Disconnected mode with internal registry mirroring
ansible-playbook ./playbooks/deploy-ocp-operators.yml \
  -i ./inventories/ocp-deployment/build-inventory.py \
  --extra-vars 'kubeconfig="/path/to/kubeconfig" disconnected=true version="4.17" operators=[...]'
```

**Setup Cluster Environment:**
```bash
ansible-playbook ./playbooks/setup-cluster-env.yml --extra-vars 'release=4.17'
```

### Linting
```bash
# Ansible linting
ansible-lint

# YAML linting
yamllint playbooks/
```

### Container Image Build
```bash
# Build container image
podman build -f Containerfile -t eco-ci-cd:latest .
```

### Running Tests
```bash
# Run Chainsaw DAST tests
chainsaw test tests/dast/
```

## Architecture Overview

### Inventory Management
The repository uses a **dynamic inventory system** centered around `inventories/ocp-deployment/build-inventory.py`. Inventory data is stored in structured directories:
- `inventories/ocp-deployment/group_vars/` - Group-level variables
- `inventories/ocp-deployment/host_vars/` - Host-specific variables (bastion, workers, masters, hypervisors)
- `inventories/cnf/` - CNF testing inventories
- `inventories/infra/` - Infrastructure inventories

### Deployment Workflow Pattern
OpenShift deployments follow an agent-based installation pattern with several key phases:

1. **Environment Preparation** (Bastion Setup)
   - Install dependencies and extract OpenShift installer
   - Use `ocp_version_facts` role to retrieve release information
   - Configure HTTP storage for artifacts

2. **Manifest Generation**
   - Generate installation manifests using `redhatci.ocp.generate_manifests`
   - Support for additional custom manifests via `extra_manifests` variable
   - Generate agent ISO with `redhatci.ocp.generate_agent_iso`

3. **Virtual Infrastructure Setup**
   - Setup sushy tools for out-of-band interface emulation on KVM hosts
   - Deploy VMs on hypervisors using `redhatci.ocp.create_vms`
   - Process KVM nodes to set proper facts

4. **Node Provisioning and Booting**
   - Boot bare-metal workers and virtual masters using `redhatci.ocp.boot_iso`
   - Monitor installation with `redhatci.ocp.monitor_agent_based_installer`

5. **Post-Installation Configuration**
   - Configure cluster pull secrets for additional trusted registries
   - Optional: Setup internal registry with DNS and CA trust (when `internal_registry=true`)

### Disconnected/Air-Gapped Pattern
When `internal_registry=true` or `disconnected=true`:
- Bastion hosts internal container registry on port 5000
- DNS (dnsmasq) configured to resolve registry URL to bastion IP
- Registry CA certificate added to cluster trust via ConfigMap
- Pull secrets updated with registry credentials
- Operators mirrored using `ocp_operator_mirror` role before installation

### Network Configuration
Nodes support **dynamic network interface configuration** via environment variables:
- `<inventory_hostname>_EXTERNAL_INTERFACE` - Network interface name (e.g., `worker0_EXTERNAL_INTERFACE=eth2`)
- `<inventory_hostname>_MAC_ADDRESS` - MAC address (e.g., `worker0_MAC_ADDRESS=aa:bb:cc:aa:bb:cc`)

This allows flexible network setup without modifying inventory files directly.

### Operator Deployment Pattern
The `deploy-ocp-operators.yml` playbook supports both connected and disconnected flows:
- **Connected:** Direct installation from Red Hat catalogs
- **Disconnected:** Mirror operators to internal registry, generate ImageDigestMirrorSets (IDMS) and CatalogSources, then install

Operators are defined as a list with fields: `name`, `catalog`, `nsname`, `channel`, `og_name`, `deploy_default_config`.

### Roles Architecture

**Core Infrastructure Roles** (in `playbooks/roles/`):
- `ocp_version_facts` - Retrieves and parses OpenShift version information, sets facts like `ocp_version_facts_pull_spec`, `ocp_version_facts_parsed_release`
- `oc_client_install` - Installs and manages OpenShift CLI client
- `ocp_operator_deployment` - Manages operator lifecycle via OLM
- `ocp_operator_mirror` - Mirrors operators to disconnected registries

**Infrastructure Deployment Roles** (in `playbooks/infra/roles/`):
- `kickstart_iso` - Creates custom kickstart ISO images for bare-metal
- `registry_gui_deploy` - Deploys container registry with GUI

**CNF/Compute Roles** (in `playbooks/compute/nto/roles/`):
- `configurecluster` - Configures cluster-wide performance settings (cgroups, container runtime, hugepages, machine config pools)

**Reporting Roles** (in `playbooks/reporting/roles/`):
- `junit2json` - Converts JUnit XML reports to JSON format
- `report_combine` - Combines multiple test reports (supports generic and Splunk formats)
- `report_metadata_gen` - Generates metadata for reports (supports DCI, Jenkins, and custom CI environments)
- `report_send` - Sends reports to collectors like Splunk

### Prow Integration
The `release/ci-operator/` directory contains Prow job definitions for CI/CD automation. Key concepts:
- **Step Registry**: Reusable bash scripts organized by domain (`telcov10n/functional/{domain}/{step-type}/{step-name}/`)
- **Workflows**: Compose multiple steps into pre/test/post phases
- **Environment Variables**: Shared via `SHARED_DIR` and `ARTIFACT_DIR` between steps
- Steps execute Ansible playbooks from this repository inside containerized environments

### Utility Scripts
Located in `scripts/`:
- `clone-z-stream-issue.py` - Clone and manage z-stream issues in issue trackers
- `fail_if_any_test_failed.py` - Validate test results and report failures for CI/CD pipelines
- `send-slack-notification-bot.py` - Send notifications to Slack channels

## Key Patterns and Conventions

### Variable Naming
- Use `snake_case` for all variables (e.g., `ocp_version`, `cluster_name`)
- Role-specific variables should be prefixed with role name (e.g., `ocp_operator_deployment_version`)

### File Naming
- **Playbooks**: lowercase with hyphens (e.g., `deploy-ocp-hybrid-multinode.yml`)
- **Roles**: lowercase with underscores (e.g., `ocp_operator_deployment`)
- **Templates**: descriptive names with `.j2` extension (e.g., `machineConfigPool.yml.j2`)

### Ansible Configuration
The `ansible.cfg` includes important settings:
- Custom roles path: `./playbooks/compute/nto/roles:./playbooks/infra/roles`
- Collections installed to: `./collections`
- SSH host key checking disabled for automation
- Forced color output for CI environments

### Testing Framework
Uses **Chainsaw** (Kyverno) for DAST (Dynamic Application Security Testing):
- Test suites in `tests/dast/`
- Configuration in `tests/dast/.chainsaw.yaml`
- Parallel execution (4 concurrent tests)
- Timeouts: 6m assert, 5m cleanup/delete/error, 10s apply

### CNF-Specific Architecture
CNF testing follows an **SSH-based execution pattern**:
1. Generate test scripts on bastion using Ansible templates
2. Execute tests remotely via SSH to bastion
3. Collect JUnit XML artifacts via SCP
4. Process with reporter roles for CI integration

Tests typically verify:
- Node Tuning Operator (NTO) configurations
- Performance profiles and hugepages
- Container runtime (runc vs crun)
- RT kernel configurations
- Machine config pools for CNF workloads

### Environment Setup Pattern
The `setup-cluster-env.yml` playbook implements a **version-to-cluster mapping strategy**:
- Maps OCP versions to specific cluster names (e.g., 4.20 → hlxcl7)
- Assigns primary and secondary NICs based on z-stream version
- Uses modulo arithmetic to rotate NIC assignments across z-streams
- Outputs environment files to `/tmp/` for use in CI pipelines

## Important Notes

### Version Management
- The `ocp_version_facts` role can parse: exact versions ("4.17.9"), minor releases ("4.17"), or pull specs ("quay.io/...")
- Sets standardized facts: `ocp_version_facts_major`, `ocp_version_facts_minor`, `ocp_version_facts_z_stream`, `ocp_version_facts_dev_version`

### Error Handling
- All playbooks include comprehensive error handling with block/rescue patterns
- Validation tasks use `assert` module to verify required variables
- Disconnected deployments include fallback logic for missing configurations

### Container Image Versioning
When working with test containers, ensure version alignment:
```bash
ECO_GOTESTS_ENV_VARS="-e ECO_CNF_CORE_COMPUTE_TEST_CONTAINER=quay.io/ocp-edge-qe/eco-gotests-compute-client:v${VERSION}"
```

### Multi-Version Support
Cluster assignments support multiple OCP versions simultaneously. When adding support for a new version, update the `cluster_release_map` in `setup-cluster-env.yml`.

### Role Dependencies
Major external role dependencies (from `requirements.yml`):
- `redhatci.ocp` (v2.9.1755524826) - Core OCP deployment and management
- `community.libvirt` (v1.3.0) - KVM/libvirt VM management
- `kubernetes.core` (v2.4.2) - Kubernetes API interaction
- `junipernetworks.junos` (v9.1.0) - Juniper network device automation
