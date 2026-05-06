# Telco-KPIs Testing Framework

Comprehensive Ansible automation framework for validating Telco Key Performance Indicators (KPIs) on OpenShift Edge deployments. This framework provides end-to-end testing capabilities including performance validation, deployment time tracking, hardware metadata collection, and automated report generation.

## Overview

The Telco-KPIs framework tests critical performance and deployment metrics for Red Hat OpenShift Edge clusters. Tests are executed on bastion hosts and generate JUnit XML reports for CI/CD integration plus comprehensive Markdown reports published to Gitea.

## Available Tests

### collect-node-info.yml
**Purpose**: Collects hardware metadata from spoke cluster nodes

**What it collects**:
- CPU model, cores, and architecture
- BIOS version and vendor
- Firmware versions
- NIC (Network Interface Card) details and drivers
- Microcode versions
- System manufacturer and product information

**Output**: `node-info-{spoke}.json` in shared artifacts directory

**Importance**: Must run before other tests - acts as baseline timestamp for test freshness filtering in report generation.

**Usage**:
```bash
ansible-playbook collect-node-info.yml \
  -e spoke_cluster=spree-02 \
  -e spoke_kubeconfig=/path/to/kubeconfig
```

### run-test.yml
**Purpose**: Executes performance tests on spoke cluster

**Available Tests**:
- **oslat**: OS latency validation
- **ptp**: Precision Time Protocol synchronization
- **cyclictest**: Real-time kernel latency testing
- **reboot**: Node reboot resilience testing
- **cpu_util**: CPU utilization validation

**Parameters**:
- `spoke_cluster`: Spoke cluster name (required)
- `test_name`: Test type to run (required)
- `test_duration`: Test duration in seconds (optional)
- `spoke_kubeconfig`: Path to spoke cluster kubeconfig (required)

**Output**: Timestamped directory `{test_name}-{spoke}-{YYYYMMDD-HHMMSS}` with JUnit XML reports

**Usage**:
```bash
ansible-playbook run-test.yml \
  -e spoke_cluster=spree-02 \
  -e test_name=oslat \
  -e test_duration=600 \
  -e spoke_kubeconfig=/path/to/kubeconfig
```

### run-bios-validation.yml
**Purpose**: Validates BIOS settings across cluster nodes

Ensures BIOS configurations meet required specifications for Telco workloads.

### run-rds-compare.yml
**Purpose**: Compares RDS (Reference Deployment Specification) metrics

Validates deployment against reference specifications.

### ztp-ai-deployment-time.yml
**Purpose**: Validates ZTP AI deployment time against threshold

**What it validates**:
- ZTP (Zero Touch Provisioning) deployment completes within acceptable time
- Default threshold: 2h0m (120 minutes) for Assisted Installer deployments
- Test PASSES if deployment duration ≤ threshold, FAILS otherwise

**How it works**:
1. Queries ACM (Advanced Cluster Management) resources on hub cluster using `kubernetes.core.k8s_info`
2. Uses `ztp_deployment_timeline` Ansible role to track deployment milestones
3. Measures from ClusterInstance creation to TALM ClusterGroupUpgrade completion
4. Generates comprehensive timeline analysis with milestone breakdown

**Parameters**:
- `spoke_cluster`: Spoke cluster name (required)
- `hub_cluster`: Hub cluster name (required)
- `hub_kubeconfig`: Path to hub cluster kubeconfig on bastion (required)
- `threshold_duration`: Maximum acceptable deployment time (default: "2h0m")

**Deployment Methods Supported**:
- **AI (Assisted Installer)**: Default - uses AgentClusterInstall resources
- **IBI (Image-based Install)**: Automatically detected via ImageBasedInstall resource

**Key Milestones Tracked**:
- ArgoCD Application Created (if present)
- ClusterInstance Created (SiteConfig v2 operator)
- GitOps Sync (ManagedCluster Created)
- AgentClusterInstall Created
- Discovery ISO Ready
- Agent Registered
- Agent Bound to Cluster
- Installation Started
- Installation Completed
- Import to ACM Started
- TALM CGU Completed (Ready for Workloads)

**Artifacts Generated**:
- `deployment-timeline-summary.txt`: Human-readable summary with milestone breakdown, timestamps, durations, and deltas
- `deployment-timeline.json`: Raw timeline events in JSON format (complete event history)
- `junit_ztp-ai-deployment-time.xml`: JUnit XML test result for CI/CD integration

**Example Summary Output**:
```
======================================================================
ZTP Deployment Timeline Summary
======================================================================
Hub Cluster: kni-qe-71
Bastion Host: bastion-hostname
Spoke Cluster: spree-02

Deployment Features:
  - ArgoCD Application Starting Point: Present
  - ClusterInstance Tracking: Present
  - TALM CGU Completion: Present
  - ztp-done Label: Present

Total Events Captured: 47

======================================================================
KEY MILESTONES
======================================================================
1. ClusterInstance Created | 2026-05-01T14:30:00Z | 0h0m0s | START
2. GitOps Sync (ManagedCluster Created) | 2026-05-01T14:32:15Z | 0h2m15s | +0h2m15s
3. AgentClusterInstall Created | 2026-05-01T14:33:00Z | 0h3m0s | +0h0m45s
...
11. TALM CGU Completed (Ready for Workloads) | 2026-05-01T16:15:30Z | 1h45m30s | +0h5m15s

======================================================================
WORKLOAD READINESS STATUS
======================================================================
✅ Cluster ready for workloads since: 2026-05-01T16:15:30Z (since 0h15m30s)

======================================================================
DEPLOYMENT SUMMARY
======================================================================
🚀 The deployment took 1h45m30s from ClusterInstance CR creation to TALM CGU Completed (Ready for Workloads)
```

**Usage**:
```bash
ansible-playbook ztp-ai-deployment-time.yml \
  -e spoke_cluster=spree-02 \
  -e hub_cluster=kni-qe-71 \
  -e hub_kubeconfig=/home/telcov10n/project/generated/kni-qe-71/auth/kubeconfig \
  -e threshold_duration=2h0m
```

**Test Result**:
- **PASS**: Deployment duration ≤ threshold
- **FAIL**: Deployment duration > threshold (JUnit XML contains detailed failure information)

**Integration with Report Generator**:
- Automatically included in comprehensive Markdown reports
- Timeline section appears before "Report Metadata" with expandable details
- Test Summary table includes ZTP_AI_DEPLOYMENT_TIME entry with pass/fail status
- JSON timeline file linked for detailed analysis

### generate-report.yml
**Purpose**: Generates comprehensive Markdown reports from all test artifacts

**What it does**:
1. Validates shared artifact directory exists
2. Checks for node-info JSON (hardware metadata baseline)
3. Filters test directories based on node-info timestamp (excludes stale tests from old environment configs)
4. Implements freshness check - skips generation if no new tests since last report
5. Runs `analyze-podman-test-results.py` in `telco-kpis-test-runner` container
6. Integrates ZTP deployment timeline (if available)
7. Compresses all artifacts into tarball
8. Fetches report and tarball to local artifacts directory
9. Publishes to Gitea repository (when `DEVELOPMENT_MODE=true`)

**Parameters**:
- `spoke_cluster`: Spoke cluster to generate report for (required)
- `test_filter`: Filter to specific tests (optional, comma-separated: oslat,ptp,cyclictest,reboot,cpu_util,ztp-ai-deployment-time)
- `output_filename`: Custom report filename (optional, auto-generated if empty: `telco-kpis-report-{spoke}-{timestamp}.md`)
- `timestamp`: UTC timestamp for report generation (optional, auto-generated if empty)

**Test Freshness Logic**:
- Reads `collected_at` timestamp from `node-info-{spoke}.json`
- Compares each test directory timestamp against node-info timestamp
- **Includes** tests with timestamp ≥ node-info timestamp (tests ran after environment update)
- **Excludes** tests with timestamp < node-info timestamp (tests ran before environment update)
- **Deletes** excluded test data from bastion to save disk space
- Displays filtering summary: tests included vs. tests excluded

**Report Action**:
- **NEW REPORT**: Created when tests are excluded (environment configuration changed)
- **UPDATE REPORT**: Created when no tests excluded (environment stable, adding new test results)

**Freshness Check**:
- Clones Gitea repository to check last report commit timestamp
- Compares test artifact timestamps against last report timestamp
- **Skips generation** if no test artifacts are newer than last report (avoids duplicate reports)
- **Generates report** if new tests detected or no previous report exists

**ZTP Deployment Timeline Integration**:
- Finds latest `ztp-ai-deployment-time-{spoke}-{YYYYMMDD-HHMMSS}` directory
- Reads `deployment-timeline-summary.txt` and `deployment-timeline.json`
- Inserts timeline section BEFORE "Report Metadata" with expandable details
- Adds ZTP_AI_DEPLOYMENT_TIME entry to Test Summary table
- Copies JSON file to report artifacts with relative link
- Removes unwanted metadata lines (Script, Data Source)

**Output Files**:
- `{output_filename}`: Markdown report (default: `telco-kpis-report-{spoke}-{timestamp}.md`)
- `{spoke}-artifacts-{timestamp}.tar.gz`: Compressed tarball of all source artifacts
- Saved to: `{{ lookup('env', 'ARTIFACT_DIR') | default('/artifacts', true) }}/reports/`

**Shared Artifact Directory Structure**:
```
/home/telcov10n/telco-kpis-artifacts/{spoke}/
├── node-info-{spoke}.json                          # Hardware metadata (baseline)
├── oslat-{spoke}-{YYYYMMDD-HHMMSS}/               # Performance test results
├── ptp-{spoke}-{YYYYMMDD-HHMMSS}/
├── cyclictest-{spoke}-{YYYYMMDD-HHMMSS}/
├── ztp-ai-deployment-time-{spoke}-{YYYYMMDD-HHMMSS}/  # Deployment timeline
│   ├── deployment-timeline-summary.txt
│   ├── deployment-timeline.json
│   └── junit_ztp-ai-deployment-time.xml
└── ...
```

**Usage**:
```bash
ansible-playbook generate-report.yml \
  -e spoke_cluster=spree-02 \
  -e test_filter=oslat,ptp,cyclictest,ztp-ai-deployment-time \
  -e output_filename=telco-kpis-report-spree-02-20260504-120000.md
```

**Task File**: Shared task file `tasks/generate-report.yml` imported by main playbook

## Roles

### ztp_deployment_timeline
**Location**: `playbooks/roles/ztp_deployment_timeline/`

**Purpose**: Tracks ZTP deployment timeline from ClusterInstance creation to TALM CGU completion

**How it works**:
1. Queries ACM resources on hub cluster using `kubernetes.core.k8s_info` module
2. Validates spoke cluster exists (ManagedCluster resource)
3. Validates ClusterInstance exists (SiteConfig v2 deployment)
4. Validates TALM ClusterGroupUpgrade exists and has completed
5. Determines deployment method (AI vs IBI)
6. Extracts timeline events from resource status conditions and timestamps
7. Calculates deployment duration
8. Generates detailed human-readable summary (when `generate_detailed_summary: true`)

**Resources Queried**:
- ClusterInstance (siteconfig.open-cluster-management.io/v1alpha1)
- ManagedCluster (cluster.open-cluster-management.io/v1)
- AgentClusterInstall (extensions.hive.openshift.io/v1beta1)
- ImageBasedInstall (extensions.hive.openshift.io/v1alpha1)
- TALM ClusterGroupUpgrade (ran.openshift.io/v1alpha1)

**Facts Exported**:
- `ztp_deployment_timeline_success`: Boolean - collection succeeded
- `ztp_deployment_timeline_events`: List of timeline events with timestamps and milestones
- `ztp_deployment_timeline_start_time`: ClusterInstance creation timestamp
- `ztp_deployment_timeline_end_time`: TALM CGU completion timestamp
- `ztp_deployment_timeline_duration_seconds`: Deployment duration in seconds
- `ztp_deployment_timeline_duration_formatted`: Formatted duration (e.g., "1h45m30s")
- `ztp_deployment_timeline_deployment_method`: "AI" or "IBI"
- `ztp_deployment_timeline_detailed_summary`: Human-readable summary (when `generate_detailed_summary: true`)

**Usage**:
```yaml
- name: Collect ZTP deployment timeline
  ansible.builtin.include_role:
    name: ztp_deployment_timeline
  vars:
    spoke_cluster: "spree-02"
    hub_kubeconfig: "/home/telcov10n/project/generated/kni-qe-71/auth/kubeconfig"
    hub_cluster: "kni-qe-71"
    generate_detailed_summary: true
```

### gitea
**Location**: `playbooks/telco-kpis/roles/gitea/`

**Purpose**: Manages Gitea repository deployment and report publishing

See `roles/gitea/README.md` for detailed documentation.

## Artifact Directory Pattern

All tests follow a consistent artifact directory pattern for compatibility with the report generator:

**Location**: `/home/telcov10n/telco-kpis-artifacts/{spoke}/` on bastion host

**Directory Naming**: `{test-name}-{spoke}-{YYYYMMDD-HHMMSS}` (UTC timestamp)

**Why UTC timestamps?**
- Ensures correct chronological ordering across different bastion timezones
- Enables accurate freshness comparison in report generator
- Prevents EDT/EST timestamp collisions during DST transitions

**Shared Artifacts Directory Structure**:
```
/home/telcov10n/telco-kpis-artifacts/
├── spree-02/
│   ├── node-info-spree-02.json                                    # Hardware metadata baseline
│   ├── oslat-spree-02-20260501-143000/                           # Test results
│   │   ├── junit_oslat.xml
│   │   └── oslat-results.json
│   ├── ptp-spree-02-20260501-144500/
│   ├── cyclictest-spree-02-20260501-150000/
│   ├── ztp-ai-deployment-time-spree-02-20260501-161530/          # Deployment timeline
│   │   ├── deployment-timeline-summary.txt
│   │   ├── deployment-timeline.json
│   │   └── junit_ztp-ai-deployment-time.xml
│   └── ...
└── spree-03/
    └── ...
```

## Typical Testing Workflow

1. **Deploy ZTP cluster** (prerequisite - cluster must exist and be managed by ACM)

2. **Run ZTP deployment time validation** (requires hub cluster kubeconfig):
   ```bash
   ansible-playbook ztp-ai-deployment-time.yml \
     -e spoke_cluster=spree-02 \
     -e hub_cluster=kni-qe-71 \
     -e hub_kubeconfig=/home/telcov10n/project/generated/kni-qe-71/auth/kubeconfig \
     -e threshold_duration=2h0m
   ```

3. **Collect hardware metadata** (establishes freshness baseline):
   ```bash
   ansible-playbook collect-node-info.yml \
     -e spoke_cluster=spree-02 \
     -e spoke_kubeconfig=/tmp/spree-02-kubeconfig
   ```

4. **Run performance tests**:
   ```bash
   # OSLAT test
   ansible-playbook run-test.yml \
     -e spoke_cluster=spree-02 \
     -e test_name=oslat \
     -e test_duration=600 \
     -e spoke_kubeconfig=/tmp/spree-02-kubeconfig

   # PTP test
   ansible-playbook run-test.yml \
     -e spoke_cluster=spree-02 \
     -e test_name=ptp \
     -e spoke_kubeconfig=/tmp/spree-02-kubeconfig

   # Cyclictest
   ansible-playbook run-test.yml \
     -e spoke_cluster=spree-02 \
     -e test_name=cyclictest \
     -e test_duration=600 \
     -e spoke_kubeconfig=/tmp/spree-02-kubeconfig
   ```

5. **Generate comprehensive report**:
   ```bash
   ansible-playbook generate-report.yml \
     -e spoke_cluster=spree-02
   ```

## Report Generation Details

The report generator (`generate-report.yml`) implements several intelligent features:

### Test Freshness Filtering
- Reads `collected_at` timestamp from `node-info-{spoke}.json` (hardware metadata baseline)
- Converts to UTC format: `YYYYMMDD-HHMMSS`
- Compares each test directory timestamp against node-info timestamp
- **Includes** tests with timestamp ≥ node-info timestamp (current environment config)
- **Excludes** and **deletes** tests with timestamp < node-info timestamp (old environment config)
- Displays summary: tests included vs. tests excluded

**Why this matters:**
- Environment configuration changes (NIC swap, BIOS update, etc.) invalidate old test results
- Prevents mixing results from different hardware configurations in same report
- Automatically cleans up stale test data to save disk space

### Freshness Check (Skip Duplicate Reports)
- Clones Gitea repository to check last report commit timestamp
- Compares test artifact timestamps against last report timestamp
- **Skips generation** if no new tests since last report (avoids duplicate reports)
- **Generates report** if:
  - No previous report exists
  - New test artifacts detected (timestamp > last report timestamp)

**Example Output**:
```
Test Freshness Check
===========================================
Gitea repository: http://bastion:3000/telcov10n/telco-kpis-reports.git
Last report generated: 2026-05-04 10:30:15 -0400
Last report UTC timestamp: 20260504-143015
Freshness check result: FOUND_NEW_TESTS: 3
===========================================
```

### ZTP Deployment Timeline Integration
When `ztp-ai-deployment-time` test artifacts are available:
1. Finds latest `ztp-ai-deployment-time-{spoke}-{YYYYMMDD-HHMMSS}` directory
2. Checks for `deployment-timeline-summary.txt`
3. Inserts timeline section **before** "Report Metadata" section
4. Creates expandable details section with full timeline summary
5. Links to `deployment-timeline.json` for raw event data
6. Extracts test result (PASS/FAIL) and duration
7. Adds entry to Test Summary table
8. Removes unwanted metadata lines (Script, Data Source)

**Report Structure**:
```markdown
# Telco-KPIs Report: spree-02

## Test Summary
| Test | Status | Result | Duration | Description |
|------|--------|--------|----------|-------------|
| **OSLAT** | ✅ Ran | ✅ PASS | 10m15s | OS latency validation |
| **ZTP_AI_DEPLOYMENT_TIME** | ✅ Ran | ✅ PASS | 1h45m30s | Start→TALM CGU Complete |

---

## ZTP Deployment Timeline

This section shows the complete ZTP/ACM deployment timeline for the spoke cluster...

**📊 [View Raw Timeline JSON](ztp-ai-deployment-time/deployment-timeline.json)**

<details>
<summary><b>Click to expand deployment timeline details</b></summary>

```
======================================================================
ZTP Deployment Timeline Summary
======================================================================
...
```

</details>

---

## Report Metadata
- **Generated**: 2026-05-04 14:30:00 UTC
- **Spoke Cluster**: spree-02
...
```

## Jenkins Integration

All telco-kpis tests have corresponding Jenkins jobs in the **Telco-KPIs** view:
- `telco-kpis-collect-node-info`
- `telco-kpis-run-test`
- `telco-kpis-run-bios-validation`
- `telco-kpis-run-rds-compare`
- `telco-kpis-ztp-ai-deployment-time`
- `telco-kpis-generate-report`

See `repos/telco-auto-ci-cd/CLAUDE.md` for detailed Jenkins job documentation.

## Troubleshooting

### Common Issues

See `docs/troubleshooting/` for detailed troubleshooting guides:
- `prometheus-pod-stuck-reboot-test-blocker.md` - Reboot test execution issues
- `k8s-exec-ipv6-fallback-issue.md` - IPv6 fallback issues with kubernetes.core.k8s_exec

### Gitea Publishing Issues

See `roles/gitea/README.md` for Gitea-specific troubleshooting.

## References

- **Parent Repository Documentation**: See `repos/eco-ci-cd/CLAUDE.md` for architecture overview
- **Jenkins Jobs Documentation**: See `repos/telco-auto-ci-cd/CLAUDE.md` for Jenkins job details
- **Gitea Role**: See `roles/gitea/README.md` for report publishing details
