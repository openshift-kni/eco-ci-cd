# NROP Test Process - Comprehensive Technical Report

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [What is NROP?](#what-is-nrop)
3. [Architecture Overview](#architecture-overview)
4. [Component Roles](#component-roles)
5. [End-to-End Test Process](#end-to-end-test-process)
6. [Test Details and Validation](#test-details-and-validation)
7. [Configuration Profiles](#configuration-profiles)
8. [Key Files and Locations](#key-files-and-locations)
9. [External Dependencies](#external-dependencies)

---

## Executive Summary

NROP (NUMA Resources Operator) testing is a comprehensive validation framework for the OpenShift NUMA Resources Operator, which is a critical component of the Telco CNF (Cloud Native Function) stack. This testing validates that OpenShift can properly manage NUMA (Non-Uniform Memory Access) topology for telecommunications workloads that require strict CPU and memory affinity for performance-sensitive applications.

The testing infrastructure uses Jenkins for orchestration, Ansible for cluster configuration, containerized Ginkgo tests for validation, and integrates with Polarion and ReportPortal for test management and reporting.

---

## What is NROP?

### NUMA Resources Operator Overview

**NROP** stands for **NUMA Resources Operator** (full name: `numaresources-operator`).

### What is NUMA?

**NUMA (Non-Uniform Memory Access)** is a computer memory design used in multiprocessor systems where memory access time depends on the memory location relative to the processor. In NUMA systems:
- Each CPU has local memory with fast access
- Remote memory (attached to other CPUs) has slower access
- Proper NUMA awareness is critical for performance-sensitive workloads

### Why NROP Matters for Telco

In telecommunications (Telco) edge deployments:
- **Low Latency**: Network functions (like 5G base stations) require ultra-low latency
- **Deterministic Performance**: Workloads must have predictable, consistent performance
- **Resource Isolation**: Critical workloads need dedicated CPU cores and local memory
- **NUMA Affinity**: Pods must be scheduled on the same NUMA node as their resources (CPUs, devices, memory)

The NUMA Resources Operator:
1. Exposes NUMA topology information to the Kubernetes scheduler
2. Ensures pods requesting specific resources are placed on appropriate NUMA nodes
3. Provides visibility into NUMA resource allocation across the cluster
4. Integrates with the Topology-Aware Scheduler for optimal pod placement

---

## Architecture Overview

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Jenkins CI/CD Pipeline                       │
│  (jenkins/jobs/testing/ocp-nrop-tests.groovy)                       │
└────────────┬────────────────────────────────────────────────────────┘
             │
             ├──> 1. Clone ocp-edge repository
             │         (Ansible playbooks and configurations)
             │
             ├──> 2. Setup Test Environment (Ansible)
             │         • Create Python virtual environment
             │         • Configure cluster for NROP testing
             │         • Set topology manager policy
             │
             ├──> 3. Deploy NROP Operator (via OLM)
             │         • Install numaresources-operator from catalog
             │         • Configure NUMAResourcesScheduler CR
             │
             ├──> 4. Run Test Suite (Containerized Ginkgo)
             │         • Standard tests (pod/container scope)
             │         • Device tests (with sample devices)
             │         • Scheduler restart tests
             │         • Reboot tests
             │         • Must-gather validation
             │
             └──> 5. Collect Results & Report
                       • Archive JUnit XML results
                       • Upload to Polarion
                       • Upload to ReportPortal
                       • Send email notifications
```

### Test Environment Structure

```
┌────────────────────────────────────────────────────────────────┐
│                    Baremetal Cluster (Disconnected)             │
│                                                                 │
│  ┌───────────────────┐  ┌───────────────────┐                 │
│  │  Master Nodes (3) │  │  Worker Nodes (2+)│                 │
│  │                   │  │                   │                 │
│  │  • OVN-Kubernetes │  │  • NUMA topology  │                 │
│  │  • Disconnected   │  │  • Sample devices │                 │
│  │  • IPv4           │  │  • Performance    │                 │
│  │                   │  │    Profile/       │                 │
│  │                   │  │    KubeletConfig  │                 │
│  └───────────────────┘  └───────────────────┘                 │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         NUMA Resources Operator Components               │  │
│  │                                                          │  │
│  │  • NUMAResourcesScheduler (Custom Scheduler)            │  │
│  │  • Resource Topology Exporter (DaemonSet)               │  │
│  │  • NodeResourceTopology CRs (per node)                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

---

## Component Roles

### 1. Jenkins (Orchestration Layer)

**File**: `jenkins/jobs/testing/ocp-nrop-tests.groovy`

**Responsibilities**:
- Orchestrates the entire test workflow
- Manages workspace and repository cloning
- Coordinates Ansible playbook execution
- Handles test container lifecycle (podman)
- Collects and archives test artifacts
- Reports results to multiple systems

**Key Libraries**:
- `kni-qe-ci-lib@master`: Shared Jenkins library with helper functions
  - `installPackagesVenv()`: Creates Python virtual environments
  - `checkLock()`: Manages resource locking
  - `parseZstream()`: Parses OpenShift version strings

**Configuration Parameters**:
- `HOST`: Jenkins agent label (baremetal node)
- `NROP_TEST_IMAGE_TAG`: Test container image (e.g., `quay.io/openshift-kni/numaresources-operator-tests:4.19.999-snapshot`)
- `NROP_MUSTGATHER_IMAGE`: Must-gather container image
- `VERSION`: OpenShift version (e.g., "4.19")
- `CONFIG_RESOURCE`: Configuration method (`performanceprofile` or `kubeletconfig`)
- `TOPOLOGY_MANAGER_SCOPE`: Kubernetes topology manager scope (`container` or `pod`)
- `GINKGO_FOCUS`: Regex to focus on specific tests
- `GINKGO_LABEL`: Label-based test filtering (e.g., "tier0||tier1")

### 2. Ansible (Configuration Management)

**External Repository**: `https://gitlab.cee.redhat.com/ocp-edge-qe/ocp-edge.git`

**Key Playbooks** (referenced but not visible in this repo):
- `linchpin-workspace/hooks/ansible/ocp-edge-setup/nrop_tests_setup.yaml`
  - Configures cluster for NROP testing
  - Sets topology manager scope and policy
  - Prepares test environment
  - Generates test execution scripts
- `linchpin-workspace/hooks/ansible/ocp-edge-setup/collect_nrop_mustgather.yaml`
  - Collects NROP-specific must-gather data
  - Archives debugging information
- `linchpin-workspace/hooks/ansible/ocp-edge-setup/sample-device-setup.yaml`
  - Deploys sample device plugins for testing
  - Configures example.com/deviceA, deviceB, deviceC

**Ansible Execution Flow**:
1. **Prepare Stage** (tags: `common,prepare`):
   - Configure topology manager
   - Apply performance profile or kubelet config
   - Wait for MachineConfigPool updates

2. **Script Setup Stage** (tags: `common,script-setup`):
   - Generate podman run command for tests
   - Configure test parameters
   - Set environment variables
   - Create test script at `${HOME}/nrop_test_script`

**Configuration Resources**:
- **PerformanceProfile**: Used for RT (Real-Time) kernel configurations
- **KubeletConfig**: Direct kubelet configuration for topology manager

**Topology Manager Configuration**:
```yaml
topology_manager_scope: "container"  # or "pod"
topology_manager_policy: "single-numa-node"
```

### 3. OLM (Operator Deployment)

**Jenkins Job**: `ocp-olm-setup` (called from CI profiles)

**Responsibilities**:
- Deploys numaresources-operator via Operator Lifecycle Manager
- Configures catalog sources (redhat-operators, redhat-operators-stage, redhat-operators-brew)
- Handles operator installation and subscription management

**Catalog Sources**:
- `redhat-operators`: Production operator catalog
- `redhat-operators-stage`: Staging/pre-release operators
- `redhat-operators-brew`: Brew builds for testing unreleased versions

**Operator Components Deployed**:
1. **numaresources-operator**: Main operator managing NUMA resources
2. **NUMAResourcesScheduler**: Custom scheduler CR
3. **Resource Topology Exporter**: DaemonSet collecting NUMA topology

### 4. Podman (Test Execution)

**Test Container**: `quay.io/openshift-kni/numaresources-operator-tests:X.Y.999-snapshot`

**Container Execution**:
```bash
podman run \
  --rm \
  --name nrop-container-tests \
  -v ${HOME}/nrop_dir/junit:/nrop/junit:z \
  -v ${KUBECONFIG_PATH}:/kubeconfig:z \
  -e KUBECONFIG=/kubeconfig \
  -e E2E_NROP_TEST_TEARDOWN=30s \
  -e E2E_NROP_TEST_COOLDOWN=30s \
  -e E2E_NROP_DEVICE_TYPE_1=example.com/deviceA \
  -e E2E_NROP_DEVICE_TYPE_2=example.com/deviceB \
  -e E2E_NROP_DEVICE_TYPE_3=example.com/deviceC \
  --entrypoint "/usr/local/bin/run-e2e-nrop.sh" \
  quay.io/openshift-kni/numaresources-operator-tests:4.19.999-snapshot \
  --focus "!schedrst" \
  --label-filter "tier0||tier1 && !schedrst" \
  --report-file /nrop/junit/junit.xml
```

**Test Parameters**:
- `E2E_NROP_TEST_TEARDOWN`: Time to wait when tearing down test resources
- `E2E_NROP_TEST_COOLDOWN`: Time to wait after each test for cluster stabilization
- `E2E_NROP_DEVICE_TYPE_1/2/3`: Device types available for testing
- `E2E_NROP_INFRA_SETUP_SKIP`: Skip infrastructure setup (for must-gather tests)
- `E2E_NROP_INFRA_TEARDOWN_SKIP`: Skip infrastructure teardown

### 5. Ginkgo Test Framework

**Testing Approach**:
- **Behavior-Driven Development (BDD)**: Tests written in Ginkgo/Gomega style
- **Label-Based Filtering**: Tests tagged with tier0, tier1, tier2, etc.
- **Focus/Skip Patterns**: Regex-based test selection

**Test Categories**:
- **Standard Tests**: Basic NUMA resource allocation and scheduling
- **Device Tests**: Tests involving device allocation on NUMA nodes
- **Hugepages Tests**: Memory management with huge pages
- **Schedrst Tests**: Scheduler restart/removal tests (disruptive)
- **Reboot Tests**: Tests requiring node reboots
- **Must-Gather Tests**: Validation of must-gather functionality

**Test Labels**:
- `tier0`: Critical path tests
- `tier1`: Important regression tests
- `tier2`: Extended test coverage
- `schedrst`: Scheduler restart tests (excluded by default with `!schedrst`)
- `slow`: Long-running tests

### 6. Reporting Systems

#### Polarion

**Purpose**: Test case management and results tracking

**Integration**:
- Query test cases from Polarion using complex filters
- Upload JUnit XML results
- Create test runs with version/build information
- Link results to test cases via automation script IDs

**Query Example** (from Jenkins job):
```
type:testcase AND
products.KEY:ocp AND
status:approved AND
subteam.KEY:kni AND
casecomponent.KEY:telco AND
subcomponent.KEY:cnfcomputenrop AND
caseautomation.KEY:(automated) AND
tags:NROP AND
version.KEY:4_19
```

**Test Run Title**: `"Compute - Telco_Compute_NROP_Regression_testing_Version: <version>; Build <build>"`

#### ReportPortal

**Purpose**: Real-time test execution reporting and analytics

**Features**:
- Launch tracking and history
- Failure analysis and categorization
- Test trends and statistics

**Launch Configuration**:
- Launch Name: `cnf-compute`
- Launch Description: Test environment details
- NROP-specific artifact extraction

#### Splunk (Optional)

**Purpose**: Log aggregation and analysis (disabled by default in profiles)

---

## End-to-End Test Process

### Step-by-Step Workflow

#### Phase 1: Environment Setup (Pre-Test)

**1.1 Jenkins Job Initialization**
```groovy
Location: jenkins/jobs/testing/ocp-nrop-tests.groovy
Trigger: Manual or via CI profile automation
Agent: Baremetal Jenkins agent (e.g., registry.hlxcl12.lab.eng.tlv2.redhat.com)
```

**1.2 Repository Cloning**
- Clean Jenkins workspace
- Clone ocp-edge repository (branch: master)
- Shallow clone for efficiency
- Timeout: 10 minutes, 6 retries

**1.3 Python Virtual Environment Setup**
```bash
Packages: ansible==2.9.13, jinja2==3.0, netaddr, selinux
Virtual env location: $WORKSPACE/ocp-edge-cnf-venv
```

#### Phase 2: Cluster Preparation

**2.1 NROP Test Preparation** (Stage: "Prepare for NROP tests")
```bash
Ansible Playbook: nrop_tests_setup.yaml
Tags: common, prepare
Parameters:
  - topology_manager_scope: container/pod
  - config_resource: performanceprofile/kubeletconfig
```

**Actions**:
- Apply PerformanceProfile or KubeletConfig to worker nodes
- Configure kubelet topology manager:
  - Policy: `single-numa-node` (most common for telco)
  - Scope: `container` or `pod`
- Trigger MachineConfigPool updates
- Wait for nodes to stabilize after configuration changes
- Configure SCTP (Stream Control Transmission Protocol) if needed

**Topology Manager Policies**:
- `none`: No topology hints
- `best-effort`: Prefer NUMA alignment but don't enforce
- `restricted`: Reject pods that don't fit NUMA topology
- `single-numa-node`: Require all resources on single NUMA node (typical for telco)

#### Phase 3: Operator Deployment

**3.1 OLM Setup** (via ocp-olm-setup job in CI profile)
```yaml
Catalog Source: redhat-operators / redhat-operators-stage / redhat-operators-brew
Operator: numaresources-operator
```

**Actions**:
- Create/update CatalogSource
- Create OperatorGroup (if needed)
- Create Subscription for numaresources-operator
- Wait for operator deployment
- Verify ClusterServiceVersion (CSV) is installed

**3.2 Operator Components Deployed**:
- **Operator Pod**: Manages NUMA resources lifecycle
- **Resource Topology Exporter DaemonSet**: Runs on each worker node
  - Discovers NUMA topology
  - Reports available resources per NUMA node
  - Creates/updates NodeResourceTopology CRs
- **NUMAResourcesScheduler**: Secondary scheduler for NUMA-aware pod placement

#### Phase 4: Test Script Generation

**4.1 Setup Testing Script** (Stage: "Setup testing script")
```bash
Ansible Playbook: nrop_tests_setup.yaml
Tags: common, script-setup
Output: ${HOME}/nrop_test_script
```

**Script Contains**:
- Podman run command with all parameters
- Environment variables for test configuration
- Volume mounts for kubeconfig and results
- Ginkgo focus/label filters

**Sample Generated Script**:
```bash
#!/bin/bash
podman run --rm \
  --name nrop-container-tests \
  -v /home/kni/nrop_dir/junit:/nrop/junit:z \
  -v /home/kni/clusterconfigs/auth/kubeconfig:/kubeconfig:z \
  -e KUBECONFIG=/kubeconfig \
  -e E2E_NROP_TEST_TEARDOWN=30s \
  -e E2E_NROP_TEST_COOLDOWN=30s \
  -e E2E_NROP_DEVICE_TYPE_1=example.com/deviceA \
  -e E2E_NROP_DEVICE_TYPE_2=example.com/deviceB \
  -e E2E_NROP_DEVICE_TYPE_3=example.com/deviceC \
  --entrypoint "/usr/local/bin/run-e2e-nrop.sh" \
  quay.io/openshift-kni/numaresources-operator-tests:4.19.999-snapshot \
  --focus "!schedrst" \
  --label-filter "tier0||tier1 && !schedrst" \
  --report-file /nrop/junit/junit.xml
```

#### Phase 5: Test Execution

**5.1 Standard NROP Tests** (Stage: "Run NROP tests")

**Test Run 1: Standard Tests (excluding scheduler restart)**
```bash
Script: ${HOME}/nrop_test_script
Focus: "!schedrst" (exclude scheduler restart tests)
Label: tier0||tier1 (if specified)
Duration: ~30-60 minutes
```

**What's Tested**:
- Pod scheduling with NUMA constraints
- Resource allocation across NUMA nodes
- Device allocation with NUMA affinity
- Hugepages allocation per NUMA node
- CPU and memory pinning
- NodeResourceTopology CR accuracy
- Scheduler plugin behavior
- Resource accounting and tracking

**5.2 Must-Gather Collection**
```bash
Ansible Playbook: collect_nrop_mustgather.yaml
Output: ${HOME}/must-gather.zip
```

**Collected Data**:
- Operator logs
- NodeResourceTopology CRs
- NUMAResourcesScheduler status
- DaemonSet pod logs
- Node NUMA topology information
- kubelet configuration

**5.3 Scheduler Restart Tests** (Disruptive)
```bash
Script: ${HOME}/nrop_test_script_distruptive_tests
Focus: "schedrst" (only scheduler restart tests)
Duration: ~10-20 minutes
```

**What's Tested**:
- Operator behavior when scheduler is removed
- Operator behavior when scheduler is restarted
- Recovery of scheduling functionality
- State consistency after disruption

**Modifications to Script**:
```bash
sed -i 's/!schedrst/schedrst/g' ${HOME}/nrop_test_script_distruptive_tests
sed -i 's|--report-file /nrop/junit/junit.xml|--report-file /nrop/junit/junit_schedrst.xml|g'
```

**5.4 Reboot Tests** (if RUN_REBOOT_TESTS_ONLY=true)
```bash
Focus: Tests requiring node reboots
Scope: container or pod (specified in config)
```

**What's Tested**:
- NUMA configuration persistence across reboots
- Operator recovery after node restart
- Resource topology rediscovery
- Pod rescheduling after reboot

**5.5 Must-Gather Validation Tests**
```bash
Entrypoint: /usr/local/bin/run-e2e-nrop-must-gather.sh
Purpose: Validate must-gather tool functionality
```

**What's Tested**:
- Must-gather script executes successfully
- All required data is collected
- Output format is correct
- Sensitive data is redacted

#### Phase 6: Results Collection and Reporting

**6.1 Artifact Collection**
```bash
Artifacts:
  - junit.xml (standard tests)
  - junit_schedrst.xml (scheduler restart tests)
  - must-gather.zip (debugging data)
  - builds.urls (related builds for tracking)
```

**6.2 JUnit XML Processing**
- Jenkins reads XML files
- Generates test reports
- Archives results

**6.3 Polarion Reporting** (if CNF_POLARION_REPORTING=true)
```bash
Job: ocp-far-edge-vran-reporting
Parameters:
  - PYLARION_TITLE: Test run title
  - RESULTS_REPORT_PATH: Path to JUnit XMLs
  - UPLOAD_XML_POLARION: true
  - DELETE_NROP_SKIPPED_TESTCASES: true
  - NROP_ARTIFACTS: true
```

**Actions**:
- Extract build and operator versions from cluster
- Parse JUnit XML results
- Map test cases to Polarion IDs
- Create test run in Polarion
- Upload results with status (passed/failed/skipped)
- Delete skipped test cases from results

**6.4 ReportPortal Reporting**
```bash
Parameters:
  - LAUNCH_NAME: cnf-compute
  - UPLOAD_XML_REPORT_PORTAL: true
```

**Actions**:
- Create launch in ReportPortal
- Upload test results
- Tag with build version
- Associate with previous launches for trending

**6.5 Email Notification**
```bash
Recipients:
  - cnf-qe+ocp-edge-ci@redhat.com
  - kni-ci-results@redhat.com (CC)

Content:
  - Build status (SUCCESS/FAILURE)
  - OCP version
  - Profile name
  - Test results URL
  - Build duration
```

#### Phase 7: Cleanup

**7.1 Workspace Cleanup**
```bash
Removed:
  - must-gather.zip
  - *.xml files
  - nrop_dir
  - nrop_ds_auth_dir
  - nrop_must_gather
  - numaresources-operator-deploy
  - test_artifacts
```

**7.2 Cluster State**
- Operator remains installed (unless profile includes cleanup)
- Configuration remains applied
- NodeResourceTopology CRs persist

---

## Test Details and Validation

### What NROP Tests Validate

#### 1. NUMA Topology Discovery
**Objective**: Verify the operator correctly discovers and reports NUMA topology

**Test Scenarios**:
- NodeResourceTopology CRs are created for each node
- NUMA zones are correctly identified
- CPU lists per NUMA node are accurate
- Memory capacity per NUMA node is reported
- Device allocations are tracked per NUMA node

**Example NodeResourceTopology CR**:
```yaml
apiVersion: topology.node.k8s.io/v1alpha1
kind: NodeResourceTopology
metadata:
  name: worker-0
spec:
  zones:
    - name: node-0
      type: Node
      resources:
        - name: cpu
          capacity: "24"
          available: "20"
        - name: memory
          capacity: "128Gi"
          available: "120Gi"
        - name: example.com/deviceA
          capacity: "4"
          available: "4"
    - name: node-1
      type: Node
      resources:
        - name: cpu
          capacity: "24"
          available: "24"
        - name: memory
          capacity: "128Gi"
          available: "128Gi"
```

#### 2. NUMA-Aware Pod Scheduling
**Objective**: Ensure pods requesting NUMA-aligned resources are scheduled correctly

**Test Scenarios**:
- Pods with CPU requests are placed on single NUMA node
- Pods with device requests get devices from same NUMA node as CPUs
- Pods with hugepages get memory from same NUMA node
- Pods with combined resource requests (CPU + device + hugepages) maintain affinity
- Scheduling fails appropriately when resources can't be aligned

**Resource Combinations Tested**:
```yaml
# Test 1: CPU only
resources:
  requests:
    cpu: "4"
    memory: "4Gi"

# Test 2: CPU + Device
resources:
  requests:
    cpu: "4"
    memory: "4Gi"
    example.com/deviceA: "1"

# Test 3: CPU + Hugepages
resources:
  requests:
    cpu: "4"
    memory: "4Gi"
    hugepages-1Gi: "2Gi"

# Test 4: CPU + Device + Hugepages
resources:
  requests:
    cpu: "4"
    memory: "4Gi"
    example.com/deviceA: "1"
    hugepages-1Gi: "2Gi"
```

#### 3. Resource Accounting
**Objective**: Verify resource tracking is accurate after pod placement

**Test Scenarios**:
- NodeResourceTopology CRs update after pod scheduling
- Available resources decrease correctly
- Resources are released when pods terminate
- Resource fragmentation is handled correctly
- Multiple pods on same node maintain separate NUMA alignment

#### 4. Topology Manager Integration
**Objective**: Validate integration with Kubernetes Topology Manager

**Test Scenarios with Different Scopes**:

**Container Scope** (`topology_manager_scope: container`):
- Each container in a pod can be on different NUMA nodes
- Resources are allocated per-container
- More flexible but less strict alignment

**Pod Scope** (`topology_manager_scope: pod`):
- All containers in a pod must be on same NUMA node
- Resources are allocated at pod level
- Stricter alignment for better performance

**Policy Validation** (`topology_manager_policy: single-numa-node`):
- Pods are rejected if resources can't fit on single NUMA node
- Admission is blocked appropriately
- Error messages are clear and actionable

#### 5. Device Allocation
**Objective**: Verify device plugins work correctly with NUMA awareness

**Test Scenarios**:
- Sample devices (deviceA, deviceB, deviceC) are allocated
- Devices are from same NUMA node as pod CPUs
- Device counts are tracked accurately
- Device health checks work correctly
- Multiple device types can be requested together

**Sample Device Plugin**:
- Deployed via `sample-device-setup.groovy` job
- Creates example.com/deviceA, deviceB, deviceC
- Each device type has multiple instances
- Distributed across NUMA nodes

#### 6. Scheduler Resilience
**Objective**: Ensure system recovers from scheduler disruptions

**Schedrst Tests** (Scheduler Restart):
- Remove NUMAResourcesScheduler CR
- Verify operator recreates it
- Confirm scheduling continues
- Validate no resource leaks occur
- Test pod rescheduling after recovery

**Test Flow**:
1. Schedule pods with NROP scheduler
2. Delete NUMAResourcesScheduler CR
3. Verify operator detects deletion
4. Operator recreates scheduler
5. New pods can be scheduled
6. Existing pods maintain placement

#### 7. Hugepages Management
**Objective**: Validate hugepages allocation with NUMA affinity

**Test Scenarios**:
- Hugepages-1Gi allocation from specific NUMA node
- Hugepages-2Mi allocation from specific NUMA node
- Combination of different hugepage sizes
- Hugepages + regular memory requests
- Accounting for hugepages in NodeResourceTopology

#### 8. Operator Upgrade and Downgrade
**Objective**: Ensure operator handles version changes gracefully

**Test Scenarios** (in upgrade profiles):
- Upgrade from previous version to current
- Downgrade scenarios (if supported)
- CRD schema compatibility
- Configuration persistence
- No disruption to running workloads

#### 9. Must-Gather Functionality
**Objective**: Validate debugging tool works correctly

**Test Scenarios**:
- Must-gather script executes without errors
- All NROP-related resources are collected:
  - Operator logs
  - NodeResourceTopology CRs
  - NUMAResourcesScheduler configuration
  - DaemonSet status and logs
  - Node NUMA topology from /sys
  - kubelet configuration
- Output is properly packaged
- Sensitive data (secrets, tokens) is redacted

#### 10. Reboot Scenarios
**Objective**: Validate persistence and recovery after node reboots

**Test Scenarios**:
- Configuration survives reboot
- Operator rediscovers topology after reboot
- Pods are rescheduled correctly
- NodeResourceTopology CRs are regenerated
- No orphaned resources remain

---

## Configuration Profiles

### Profile Types

#### 1. Stage Profiles (`*-nrop-stage_functests.yaml`)
**Purpose**: Testing with staging operator builds

**Configuration**:
```yaml
olm_catalog_source: redhat-operators-stage
operators_list: "numaresources-operator"
```

**Use Cases**:
- Pre-release operator validation
- Early access to new features
- Integration testing before GA

#### 2. Production Profiles (`*-nrop-prod_functests.yaml`)
**Purpose**: Testing with production operator releases

**Configuration**:
```yaml
olm_catalog_source: redhat-operators
operators_list: "numaresources-operator"
ginkgo_label: "tier0||tier1"  # Only critical tests
```

**Use Cases**:
- GA release validation
- Customer-facing builds
- Production readiness verification

**Differences from Stage**:
- Uses production catalog
- Runs fewer tests (tier0/tier1 only) for faster feedback
- Higher confidence requirement for success

#### 3. Brew Profiles (`*-nrop-brew_functests.yaml`)
**Purpose**: Testing with unreleased Brew builds

**Configuration**:
```yaml
olm_catalog_source: redhat-operators-brew
operators_list: "numaresources-operator"
nrop_brew_build_number: ${VERSION}
```

**Use Cases**:
- Testing specific Brew builds
- Regression testing during development
- Validating fixes before release

**Additional Jobs**:
- Includes `ocp-cnf-cert-tests` with `CNF_CERT_NUMA_RESOURCES: true`
- CNF certification testing for NROP

### Profile Job Sequence

**Typical Profile** (e.g., `bm-disconnected-ipv4-cnf-compute-nrop-stage_functests.yaml`):

```yaml
jobs:
  1. ocp-baremetal-ipi-deployment:
     - Deploy OpenShift cluster
     - Baremetal IPI installation
     - Disconnected registry
     - IPv4 networking

  2. ocp-olm-setup:
     - Install numaresources-operator via OLM
     - Configure catalog source

  3. ocp-nrop-tests (topology_manager_scope: pod):
     - Run tests with pod-level NUMA affinity
     - Report results

  4. ocp-nrop-tests (topology_manager_scope: container):
     - Run tests with container-level NUMA affinity
     - Accumulate results

  5. ocp-nrop-tests (run_reboot_tests_only: true):
     - Run reboot-specific tests
     - Validate persistence

  6. ocp-far-edge-vran-reporting:
     - Aggregate all results
     - Upload to Polarion
     - Upload to ReportPortal
```

### Test Execution Variants

**Variant 1: Full Test Suite**
```yaml
run_prepare_stages: true
run_test: true
run_reboot_tests_only: false
ginkgo_focus: ""
ginkgo_label: ""
```
- Runs all tests
- Includes setup and preparation
- No filtering applied

**Variant 2: Tier-Based Testing**
```yaml
run_prepare_stages: true
run_test: true
ginkgo_label: "tier0||tier1"
```
- Runs only tier0 and tier1 tests
- Faster execution
- Critical path validation

**Variant 3: Reboot Tests Only**
```yaml
run_prepare_stages: true
run_reboot_tests_only: true
```
- Only tests requiring reboots
- Special handling for disruptive tests
- Validates persistence

**Variant 4: Focused Testing**
```yaml
run_prepare_stages: true
run_test: true
ginkgo_focus: "devices\\|hugepages"
```
- Runs tests matching regex
- Device and hugepages tests only
- Quick validation of specific functionality

---

## Key Files and Locations

### Jenkins Jobs

| File | Purpose |
|------|---------|
| `jenkins/jobs/testing/ocp-nrop-tests.groovy` | Main NROP test orchestration job |
| `jenkins/jobs/testing/sample-device-setup.groovy` | Deploy sample device plugins |
| `jenkins/jobs/ocp-olm/ocp-olm-setup.groovy` | OLM operator installation |
| `jenkins/jobs/ocp-far-edge-vran-pipeline/ocp-far-edge-vran-xml-reporting.groovy` | Test results reporting |

### CI Profiles

| Pattern | Versions | Purpose |
|---------|----------|---------|
| `jenkins/ci-profiles-new/*/bm-disconnected-ipv4-cnf-compute-nrop-stage_functests.yaml` | 4.10-4.21 | Stage builds testing |
| `jenkins/ci-profiles-new/*/bm-disconnected-ipv4-cnf-compute-nrop-prod_functests.yaml` | 4.10-4.21 | Production builds testing |
| `jenkins/ci-profiles-new/*/bm-disconnected-ipv4-cnf-compute-nrop-brew_functests.yaml` | 4.10-4.19 | Brew builds testing |

### Profile Naming Convention
```
bm-disconnected-ipv4-cnf-compute-nrop-{catalog}_functests.yaml
│   │            │     │       │     │      └─ Test type (functional)
│   │            │     │       │     └──────── Catalog source (stage/prod/brew)
│   │            │     │       └────────────── Component (NROP)
│   │            │     └────────────────────── CNF compute workload
│   │            └──────────────────────────── IPv4 networking
│   └───────────────────────────────────────── Disconnected installation
└───────────────────────────────────────────── Baremetal deployment
```

### Runtime Files (on Jenkins Agent)

| Location | Content |
|----------|---------|
| `${WORKSPACE}/ocp-edge/` | Cloned ocp-edge repository with Ansible playbooks |
| `${WORKSPACE}/ocp-edge-cnf-venv/` | Python virtual environment for Ansible |
| `${HOME}/clusterconfigs/auth/kubeconfig` | Cluster kubeconfig file |
| `${HOME}/clusterconfigs/ocp-edge.inventory` | Ansible inventory |
| `${HOME}/clusterconfigs/extravars.yaml` | Extra variables for Ansible |
| `${HOME}/nrop_test_script` | Generated test execution script |
| `${HOME}/nrop_test_script_distruptive_tests` | Modified script for schedrst tests |
| `${HOME}/nrop_test_script_mg_entry` | Modified script for must-gather tests |
| `${HOME}/nrop_dir/junit/` | Test result JUnit XML files |
| `${HOME}/must-gather.zip` | Collected debugging information |

---

## External Dependencies

### Git Repositories

#### 1. ocp-edge Repository
**URL**: `https://gitlab.cee.redhat.com/ocp-edge-qe/ocp-edge.git`
**Branch**: `master` (configurable via `OCP_EDGE_BRANCH`)

**Contains**:
- Ansible playbooks for NROP test setup
- Configuration templates
- Test script generation logic
- Must-gather collection playbooks
- Sample device setup automation

**Key Playbooks**:
- `linchpin-workspace/hooks/ansible/ocp-edge-setup/nrop_tests_setup.yaml`
- `linchpin-workspace/hooks/ansible/ocp-edge-setup/collect_nrop_mustgather.yaml`
- `linchpin-workspace/hooks/ansible/ocp-edge-setup/sample-device-setup.yaml`

**Access**: Internal Red Hat GitLab (requires VPN and authentication)

#### 2. kni-qe-ci-lib Repository
**URL**: `https://gitlab.cee.redhat.com/ocp-edge-qe/kni-qe-ci-lib.git`
**Branch**: `master`
**Type**: Jenkins Shared Library

**Provides**:
- Helper functions for Jenkins pipelines
- Common workflow patterns
- Utility methods (venv creation, locking, etc.)

**Access**: Internal Red Hat GitLab

#### 3. cnf-polarion Repository
**URL**: `https://gitlab.cee.redhat.com/cnf/cnf-polarion.git`
**Branch**: `master`

**Provides**:
- Polarion integration scripts
- Result parsing and upload
- Test case mapping
- Report generation

**Access**: Internal Red Hat GitLab

### Container Images

#### 1. NROP Test Image
**Repository**: `quay.io/openshift-kni/numaresources-operator-tests`
**Tags**:
- `4.10.999-snapshot`
- `4.11.999-snapshot`
- ... (version-specific)
- `4.21.999-snapshot`

**Contains**:
- Ginkgo test suite
- E2E test scenarios
- Test execution scripts
- Must-gather validation

#### 2. NROP Must-Gather Image
**Repository**: `quay.io/openshift-kni/numaresources-must-gather`
**Tags**: Version-specific (matching test image)

**Contains**:
- Must-gather collection scripts
- NROP-specific debugging tools
- Log parsers and formatters

#### 3. Sample Device Plugin Image
**Repository**: `quay.io/k8stopologyawareschedwg/sample-device-plugin`
**Tag**: `v0.2.2` (default)

**Provides**:
- Example device plugin implementation
- Creates example.com/deviceA, deviceB, deviceC
- Used for device allocation testing

#### 4. Lint Image (for CI)
**Repository**: `quay.io/ocp-edge-qe/lint`
**Tag**: `latest`

**Contains**:
- yamllint, bashate, ansible-lint, flake8
- Pre-commit hooks
- Jenkins linter

### External Services

#### 1. Polarion
**Purpose**: Test case management and results tracking
**Integration**: Via REST API
**Authentication**: Username/password credentials (Jenkins secret)

**Test Run Queries**:
- Complex Lucene-style queries
- Filters by product, version, component, tags
- Maps test results to test cases

#### 2. ReportPortal
**Purpose**: Real-time test execution reporting
**Integration**: Via API
**Configuration**: Launch name, description, tags

**Features**:
- Test execution history
- Failure analysis
- Trend reporting
- Build comparisons

#### 3. Jenkins
**URL**: `https://auto-jenkins-csb-kniqe.apps.ocp-c1.prod.psi.redhat.com` (configured in GitLab CI)
**Purpose**: CI/CD orchestration
**Agents**: Baremetal lab machines (labeled by hostname)

**Agent Labels** (examples):
- `registry.hlxcl6.lab.eng.tlv2.redhat.com`
- `registry.hlxcl12.lab.eng.tlv2.redhat.com`
- `registry.kni-qe-3.lab.eng.rdu2.redhat.com`

#### 4. Red Hat Brew
**Purpose**: Internal build system
**Operator Catalog**: `redhat-operators-brew`
**Use**: Testing unreleased operator builds

#### 5. OpenShift Release Streams
**API**: `https://amd64.ocp.releases.ci.openshift.org/api/v1/releasestream/`
**Purpose**: Fetch latest OCP release images for deployment

**Example Query**:
```bash
curl -Ls https://amd64.ocp.releases.ci.openshift.org/api/v1/releasestream/4-stable/tags \
  | jq -r '[.tags[]|select(.phase == "Accepted")|select(.name | test("4\\.19\\."))][0].pullSpec'
```

### Python Dependencies

**Installed via Ansible**:
```
ansible==2.9.13
jinja2==3.0
netaddr
selinux
```

**Virtual Environment**: `${WORKSPACE}/ocp-edge-cnf-venv`

### Vault Credentials

**Jenkins Secret**: `ocm-vault-cred`
**Purpose**: Decrypt Ansible vault files containing secrets
**Location**: `linchpin-workspace/hooks/ansible/ocp-edge-setup/vault_files/ocp_secrets.yaml`

---

## Test Scenarios Deep Dive

### Scenario 1: Basic NUMA Pod Scheduling

**Test**: Verify pods with CPU requests are scheduled on a single NUMA node

**Steps**:
1. Create pod with guaranteed QoS (requests == limits)
2. Request specific number of CPUs (e.g., 4 cores)
3. Pod is scheduled by NUMAResourcesScheduler
4. Verify pod placement via NodeResourceTopology
5. Check all CPUs are from same NUMA node
6. Verify node resources are updated correctly

**Expected Result**:
- Pod scheduled successfully
- All CPUs from single NUMA node
- NodeResourceTopology.available reflects allocation

### Scenario 2: Device Affinity

**Test**: Verify devices are allocated from same NUMA node as CPUs

**Steps**:
1. Deploy sample device plugin (deviceA, deviceB, deviceC)
2. Create pod requesting CPUs and devices
3. Verify pod scheduled successfully
4. Check CPU allocation (e.g., CPUs from NUMA node 0)
5. Verify device allocated from same NUMA node
6. Confirm NodeResourceTopology accuracy

**Expected Result**:
- Pod gets CPUs and device from same NUMA node
- Resource topology updated correctly
- No cross-NUMA resource allocation

### Scenario 3: Hugepages with NUMA Affinity

**Test**: Verify hugepages allocated from same NUMA node as CPUs

**Steps**:
1. Configure hugepages on worker nodes
2. Create pod requesting CPUs and hugepages-1Gi
3. Verify pod scheduled
4. Confirm hugepages allocated from correct NUMA node
5. Check memory accounting in NodeResourceTopology

**Expected Result**:
- Hugepages from same NUMA node as CPUs
- Available hugepages decreased correctly
- Pod memory performance optimized

### Scenario 4: Resource Fragmentation Handling

**Test**: Verify scheduler handles NUMA resource fragmentation

**Setup**:
- Node has 2 NUMA nodes
- NUMA 0: 12 CPUs, 64GB RAM
- NUMA 1: 12 CPUs, 64GB RAM

**Steps**:
1. Schedule pod requesting 8 CPUs on NUMA 0
2. Remaining on NUMA 0: 4 CPUs
3. Schedule pod requesting 6 CPUs
4. Verify pod goes to NUMA 1 (can't fit on NUMA 0)
5. Check NodeResourceTopology reflects this

**Expected Result**:
- Scheduler correctly identifies NUMA 0 insufficient
- Pod placed on NUMA 1
- No partial allocation across NUMA nodes

### Scenario 5: Scheduler Removal and Recovery

**Test**: Verify operator recovers from scheduler deletion

**Steps**:
1. Verify NUMAResourcesScheduler CR exists
2. Schedule test pod successfully
3. Delete NUMAResourcesScheduler CR
4. Operator detects deletion
5. Operator recreates NUMAResourcesScheduler
6. Schedule new pod
7. Verify scheduling works correctly

**Expected Result**:
- Operator automatically recreates scheduler
- New pods can be scheduled
- No resource leaks
- Existing pods unaffected

### Scenario 6: Node Reboot Persistence

**Test**: Verify configuration persists across node reboot

**Steps**:
1. Configure cluster with topology manager
2. Schedule NUMA-aware pods
3. Record pod placements and resource allocations
4. Reboot worker node
5. Wait for node ready
6. Verify topology manager configuration applied
7. Check NodeResourceTopology recreated
8. Verify pods rescheduled correctly

**Expected Result**:
- Configuration survives reboot
- Topology rediscovered correctly
- Pods rescheduled with same constraints

---

## Troubleshooting Guide

### Common Issues

#### Issue 1: Operator Not Deploying
**Symptoms**: CSV not reaching Succeeded phase

**Checks**:
- Verify CatalogSource is healthy
- Check OperatorGroup exists
- Ensure subscription is created
- Review operator pod logs

**Resolution**:
```bash
oc get catalogsource -n openshift-marketplace
oc get subscription -n openshift-numaresources
oc get csv -n openshift-numaresources
oc logs -n openshift-numaresources deployment/numaresources-controller-manager
```

#### Issue 2: Tests Failing to Start
**Symptoms**: podman run fails, container exits immediately

**Checks**:
- Verify test image is accessible
- Check kubeconfig is mounted correctly
- Ensure RBAC permissions for service account
- Review container logs

**Resolution**:
```bash
podman pull quay.io/openshift-kni/numaresources-operator-tests:4.19.999-snapshot
oc auth can-i --list --as=system:serviceaccount:openshift-numaresources:default
cat ${HOME}/nrop_test_script  # Review generated script
```

#### Issue 3: NodeResourceTopology Not Created
**Symptoms**: CRs missing for worker nodes

**Checks**:
- Verify Resource Topology Exporter DaemonSet running
- Check node labels and taints
- Review RTE pod logs
- Ensure CRD installed

**Resolution**:
```bash
oc get daemonset -n openshift-numaresources
oc get pods -n openshift-numaresources -l app=resource-topology-exporter
oc logs -n openshift-numaresources -l app=resource-topology-exporter
oc get noderesourcetopology
```

#### Issue 4: Pods Not Scheduled
**Symptoms**: Pods pending, scheduler not placing them

**Checks**:
- Verify NUMAResourcesScheduler exists and ready
- Check scheduler pod logs
- Review pod events
- Ensure topology manager configured

**Resolution**:
```bash
oc get numaresourcesscheduler
oc get pods -n openshift-numaresources -l app=secondary-scheduler
oc describe pod <pending-pod>
oc get nodes -o jsonpath='{.items[*].metadata.annotations.kubelet\.config\.k8s\.io/kubelet}'
```

---

## Performance Considerations

### Test Duration

| Test Phase | Typical Duration |
|------------|------------------|
| Cluster Deployment | 45-60 minutes |
| Operator Installation | 5-10 minutes |
| Test Preparation | 5-10 minutes |
| Standard Tests (tier0/tier1) | 20-30 minutes |
| Full Test Suite | 40-60 minutes |
| Scheduler Restart Tests | 10-15 minutes |
| Reboot Tests | 15-25 minutes |
| Must-Gather Collection | 5-10 minutes |
| **Total (Full Profile)** | **2.5-3.5 hours** |

### Resource Requirements

**Jenkins Agent**:
- CPU: 4+ cores
- Memory: 8GB+ RAM
- Disk: 50GB+ available

**OpenShift Cluster**:
- Master nodes: 3 (HA)
- Worker nodes: 2+ (with NUMA hardware)
- Each worker:
  - 24+ CPUs (preferably 2 NUMA nodes)
  - 64GB+ RAM
  - NUMA-capable hardware

**Network**:
- Disconnected install requires local registry
- Registry storage: 100GB+

---

## Conclusion

NROP testing provides comprehensive validation of NUMA resource management in OpenShift for telecommunications workloads. The testing framework ensures that:

1. **Topology Discovery**: NUMA hardware topology is accurately discovered and reported
2. **Resource Allocation**: Pods are placed with optimal NUMA affinity for performance
3. **Scheduler Integration**: Kubernetes topology manager works correctly with NROP
4. **Device Management**: Devices (GPUs, FPGAs, NICs) maintain NUMA affinity
5. **Resilience**: System recovers gracefully from failures and disruptions
6. **Persistence**: Configuration survives reboots and cluster events

The multi-layered approach using Jenkins, Ansible, containerized tests, and comprehensive reporting ensures high confidence in NROP functionality across OpenShift versions 4.10 through 4.21+.

For telecommunications edge deployments where deterministic, low-latency performance is critical, NROP testing validates that OpenShift can meet these stringent requirements.

---

## Appendix: Glossary

| Term | Definition |
|------|------------|
| **NROP** | NUMA Resources Operator - OpenShift operator for NUMA resource management |
| **NUMA** | Non-Uniform Memory Access - memory architecture where access time depends on memory location |
| **CNF** | Cloud Native Function - containerized network functions for telco |
| **OLM** | Operator Lifecycle Manager - Kubernetes operator installation and management |
| **Ginkgo** | BDD testing framework for Go |
| **NodeResourceTopology** | CRD representing NUMA topology and resource availability per node |
| **Topology Manager** | Kubernetes feature for NUMA-aware resource allocation |
| **Single-NUMA-Node Policy** | Topology manager policy requiring all resources on one NUMA node |
| **RTE** | Resource Topology Exporter - DaemonSet collecting NUMA topology |
| **Schedrst** | Scheduler restart - disruptive tests for scheduler resilience |
| **Must-Gather** | OpenShift debugging data collection tool |
| **QoS** | Quality of Service - pod resource guarantee level (Guaranteed/Burstable/BestEffort) |
| **DU** | Distributed Unit - part of 5G RAN (Radio Access Network) |
| **RAN** | Radio Access Network - wireless network infrastructure |
| **ZTP** | Zero Touch Provisioning - automated cluster deployment via GitOps |
