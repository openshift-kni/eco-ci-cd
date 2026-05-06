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

### Telco-KPIs Testing Framework

The `playbooks/telco-kpis/` directory contains a comprehensive testing framework for validating Telco KPIs (Key Performance Indicators) on OpenShift Edge deployments. Tests generate JUnit XML reports and Markdown reports published to Gitea.

**Available Tests:**
- `collect-node-info.yml` - Collects hardware information (CPU, BIOS, firmware versions, NIC details)
- `run-test.yml` - Executes performance tests (oslat, ptp, cyclictest, reboot, cpu_util)
- `run-bios-validation.yml` - Validates BIOS settings across cluster nodes
- `run-rds-compare.yml` - Compares RDS deployment metrics
- `ztp-ai-deployment-time.yml` - **Validates ZTP AI deployment time against threshold**
- `generate-report.yml` - Generates comprehensive Markdown reports from all test artifacts

**ZTP AI Deployment Time Test** (`ztp-ai-deployment-time.yml`):
- **Purpose**: Validates that ZTP (Zero Touch Provisioning) Assisted Installer deployments complete within acceptable time threshold (default: 2h0m = 120 minutes)
- **Implementation**: Uses `ztp_deployment_timeline` Ansible role with `kubernetes.core.k8s_info` module (not bash scripts)
- **Measurement Point**: ClusterInstance creation → TALM ClusterGroupUpgrade completion
- **Test Result**: PASS if deployment duration ≤ threshold, FAIL otherwise
- **Artifacts Generated**:
  - `deployment-timeline-summary.txt` - Human-readable summary with milestone breakdown
  - `deployment-timeline.json` - Raw timeline events in JSON format
  - `junit_ztp-ai-deployment-time.xml` - JUnit XML test result for CI/CD integration
- **Output**: Timestamped directory `ztp-ai-deployment-time-{spoke}-{YYYYMMDD-HHMMSS}` in shared artifacts location

**ZTP Deployment Timeline Role** (`playbooks/roles/ztp_deployment_timeline/`):
- Queries ACM (Advanced Cluster Management) resources on hub cluster
- Tracks deployment milestones: ClusterInstance, ManagedCluster, AgentClusterInstall, TALM CGU
- Supports both AI (Assisted Installer) and IBI (Image-based Install) deployment methods
- Generates detailed milestone analysis with timestamps, durations, and deltas
- Exports facts: `ztp_deployment_timeline_duration_seconds`, `ztp_deployment_timeline_deployment_method`

**Report Generation** (`generate-report.yml`):
- Aggregates all test artifacts from shared location (`/home/telcov10n/telco-kpis-artifacts/{spoke}/`)
- Runs `analyze-podman-test-results.py` in `telco-kpis-test-runner` container
- Filters tests based on node-info timestamp (excludes stale tests from old environment configs)
- Integrates ZTP deployment timeline into report before "Report Metadata" section
- Publishes Markdown report + compressed tarball to Gitea repository
- Implements freshness check: skips generation if no new tests since last report

**Artifact Directory Pattern:**
```
/home/telcov10n/telco-kpis-artifacts/{spoke}/
├── node-info-{spoke}.json                                    # Hardware metadata (baseline)
├── {test-name}-{spoke}-{YYYYMMDD-HHMMSS}/                   # Timestamped test directories
│   ├── junit_{test-name}.xml                                # JUnit XML report
│   └── {test-specific-artifacts}
└── ztp-ai-deployment-time-{spoke}-{YYYYMMDD-HHMMSS}/
    ├── deployment-timeline-summary.txt
    ├── deployment-timeline.json
    └── junit_ztp-ai-deployment-time.xml
```

**UTC Timestamp Consistency:**
All telco-kpis tests use UTC timestamps (`date -u +%Y%m%d-%H%M%S`) to ensure correct chronological ordering and freshness comparison across different bastion timezones.

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

## Troubleshooting

### Common Post-Deployment Issues

#### Prometheus Pod Stuck (Reboot Test Blocker)
**Symptom:** Reboot tests always skip execution, prometheus-k8s-0 pod stuck in Init:0/1 state

**Impact:** CNF-gotests BeforeEach health check fails, preventing reboot tests from executing

**Workaround:** See detailed fix at `playbooks/telco-kpis/docs/troubleshooting/prometheus-pod-stuck-reboot-test-blocker.md`

**Quick Fix:**
```bash
# Fix ConfigMap and restart pod
oc --kubeconfig /tmp/<spoke>-kubeconfig apply -f <(cat <<'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: alertmanager-main-generated
  namespace: openshift-monitoring
data:
  alertmanager.yaml.gz: H4sIAAAAAAAA/0yOQQrCMBBF95wiSxeVQhcu3HoCwY1gF0k6bQOdSTOTUsRzdmgXrt7j///x5gkf4C8LDmYSaIBzWSnpoGjYo3xVdWAXQmWXCNnSPBg0SBxhzm0p2xrPo1qQVvd+hN9uRs4x8S+VQW9kF+LrO3U51OBaT02BVTwBUZs+8lAyxV3k88SYOr72yC1bX1G6t7neMu08nVmz/QMAAP//jkUArgAAAA==
EOF
)

oc --kubeconfig /tmp/<spoke>-kubeconfig delete pod prometheus-k8s-0 -n openshift-monitoring
```

**Related Bugs:** OCPBUGS-65953, OCPBUGS-70352

**Prevention:** Consider adding automated fix to post-deployment playbooks (see troubleshooting doc for implementation)

#### kubernetes.core.k8s_exec IPv6 Fallback Issue

**Symptom:** `kubernetes.core.k8s_exec` fails with `[Errno 113] No route to host` but `oc exec` works fine

**Impact:** Blocks pod exec operations in Ansible playbooks (BIOS/microcode collection, hardware info gathering)

**Root Cause:** Python `websocket-client` library does not fall back to IPv4 when IPv6 connection fails. In dual-stack DNS environments without IPv6 routing, the library tries IPv6 first and fails instead of falling back to IPv4.

**Solution:** Use `oc exec` via `ansible.builtin.shell` instead of `kubernetes.core.k8s_exec`

**Example:**
```yaml
# Instead of k8s_exec:
- name: Get BIOS version
  ansible.builtin.shell: |
    oc --kubeconfig {{ spoke_kubeconfig }} \
      -n {{ namespace }} exec {{ pod_name }} \
      -c {{ container }} -- chroot /rootfs dmidecode -t 0
  register: result
  failed_when: false
  changed_when: false
```

**Detailed Analysis:** See `playbooks/telco-kpis/docs/troubleshooting/k8s-exec-ipv6-fallback-issue.md`

**Commits:** bb5e97f (fix), 1e03b5f (related)

**Last Verified:** 2026-04-30 (spree-02 cluster)

### Troubleshooting Documentation

Additional troubleshooting guides are available in:
- `playbooks/telco-kpis/docs/troubleshooting/` - Telco-KPIs specific issues
- `playbooks/telco-kpis/roles/gitea/README.md` - Gitea report publishing issues
