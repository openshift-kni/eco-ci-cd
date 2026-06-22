# Hub Lockdown Parse Tests

Molecule-based tests for the unified lockdowns role (hub scenario).

## Overview

These tests validate the hub lockdown **parse** logic without requiring a real OpenShift cluster:
- ✅ Download and parse hub lockdown JSON from URI
- ✅ Validate JSON structure (hub.ocp, hub.operators, hub.metadata)
- ✅ Set facts correctly (hub_lockdown_operators, hub_ocp_version, hub_ocp_pull_spec)
- ✅ Verify catalog name mappings (redhat/certified/community/FBC)
- ✅ Verify operator field completeness
- ✅ Verify OperatorGroup spec handling

## Test Structure

```
molecule/hub/default/
├── molecule.yml     # Podman test configuration
├── prepare.yml      # Creates mock hub-lockdown.json file
├── converge.yml     # Calls lockdowns role (mode=hub, action=parse)
├── verify.yml       # Validates parse results (10 test assertions)
└── test.yml         # Runs all phases in sequence
```

## Running Tests

### Option 1: Using Makefile (Recommended)

```bash
cd playbooks/telco-kpis/roles/lockdowns
make test-hub
```

### Option 2: Using Molecule Directly

```bash
cd playbooks/telco-kpis/roles/lockdowns
molecule test -s hub
```

### Option 3: Individual Phases (Local Ansible)

```bash
cd playbooks/telco-kpis/roles/lockdowns
make prepare-hub   # Create mock lockdown JSON
make converge-hub  # Run parse action
make verify-hub    # Run assertions
```

## Test Scenarios

### TEST 1: hub_lockdown_operators fact set
Verifies that the parse action sets `hub_lockdown_operators` fact with 6 operators.

### TEST 2: Hub OCP version facts
Verifies that `hub_ocp_version` and `hub_ocp_pull_spec` facts are set correctly from lockdown JSON.

### TEST 3-6: Catalog Name Mapping
Validates that catalog names from lockdown JSON are preserved:
- Redhat operators → `redhat-operators`
- Certified operators → `certified-operators`
- Community operators → `community-operators`
- FBC operators → unchanged (e.g., `topology-aware-lifecycle-manager-fbc`)

### TEST 7: Operator Field Completeness
Ensures all 9 required fields are present for each operator:
- name, namespace, catalog, channel
- subscription_name, installed_csv, install_plan_approval
- og_name, og_spec

### TEST 8: OperatorGroup Spec Handling
Validates correct handling of empty vs populated OperatorGroup specs:
- Global operators → `og_spec: {}`
- Namespaced operators → `og_spec: {targetNamespaces: [...]}`

### TEST 9: Specific Operator Details
Spot-checks specific operator values:
- MCE channel: `stable-2.10`
- ACM channel: `release-2.15`
- MCE CSV: `multicluster-engine.v2.10.3`

### TEST 10: hub_lockdown_data Structure
Verifies that `hub_lockdown_data` fact contains complete parsed JSON with metadata.

## Mock Data

The prepare phase creates a mock hub lockdown JSON at `/tmp/hub-lockdown.json` with:
- 6 operators (MCE, ACM, TALM, LSO, certified-example, community-example)
- OCP version 4.21.20
- Mixed catalog types (redhat, certified, community, FBC)
- Mixed OperatorGroup specs (empty and populated)

## Expected Output

```
==========================================
  Lockdowns Role (Hub Parse) Tests: ALL PASSED
==========================================
✓ hub_lockdown_operators fact set correctly
✓ Hub OCP version facts correct
✓ Redhat operator catalogs correct
✓ Certified operator catalogs correct
✓ Community operator catalogs correct
✓ FBC catalogs unchanged
✓ All operator fields present
✓ OperatorGroup specs handled correctly
✓ Specific operator details correct
✓ hub_lockdown_data structure valid
==========================================
```

## What This Tests

**Parse Action Only**: These tests validate the `lockdowns` role's ability to:
1. Download lockdown JSON from URI (using `file://` for local testing)
2. Parse JSON and validate structure
3. Set facts for use in deployment playbooks

**Capture Action**: Not tested here (TODO - requires implementing hub/capture.yml logic)

## Continuous Integration

Add to CI pipeline:

```yaml
test-lockdowns-hub:
  script:
    - cd playbooks/telco-kpis/roles/lockdowns
    - ansible-playbook -i localhost, -c local molecule/hub/default/test.yml
```

## Related Files

- Role tasks: `playbooks/telco-kpis/roles/lockdowns/tasks/hub/parse.yml`
- Common tasks: `playbooks/telco-kpis/roles/lockdowns/tasks/common/`
- Template: `playbooks/telco-kpis/roles/lockdowns/templates/hub/lockdown.json.j2`
- Wrapper playbook: `playbooks/telco-kpis/deploy-ocp-operators.yml`
