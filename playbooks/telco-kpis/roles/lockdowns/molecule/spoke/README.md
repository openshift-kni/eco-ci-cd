# Spoke Lockdown Tests

Molecule-based tests for the unified lockdowns role (spoke scenario).

## Overview

These tests validate the spoke lockdown **parse** and **generate** logic without requiring real operator mirroring:
- ✅ Parse legacy format lockdowns
- ✅ Parse new format lockdowns (future compatible)
- ✅ Dual format compatibility (both produce same output facts)
- ✅ Generate lockdown JSON from accumulated metadata
- ✅ Verify no omit placeholders in generated pull specs
- ✅ Validate JSON structure and operator field completeness

## Test Structure

```
molecule/spoke/default/
├── molecule.yml     # Podman test configuration
├── prepare.yml      # Creates mock lockdown files (legacy + new) and metadata
├── converge.yml     # Runs parse (both formats) and generate tasks
├── verify.yml       # Validates parse and generate results (17 test assertions)
└── test.yml         # Runs all phases in sequence
```

## Running Tests

### Option 1: Using Makefile (Recommended)

```bash
cd playbooks/telco-kpis/roles/lockdowns
make test-spoke
```

### Option 2: Using Molecule Directly

```bash
cd playbooks/telco-kpis/roles/lockdowns
molecule test -s spoke
```

### Option 3: Individual Phases (Local Ansible)

```bash
cd playbooks/telco-kpis/roles/lockdowns
ansible-playbook -i localhost, -c local molecule/spoke/default/prepare.yml
ansible-playbook -i localhost, -c local molecule/spoke/default/converge.yml
ansible-playbook -i localhost, -c local molecule/spoke/default/verify.yml
```

## Test Scenarios

### PARSE TESTS (Legacy Format)

**TEST 1-5**: Legacy format parse validation
- Format detection (deployment key at root)
- Operator count (3 operators)
- OCP version extraction (4.22)
- OCP pull spec extraction
- Operator field completeness (name, catalog, nsname, channel, bundle, fbc)

### PARSE TESTS (New Format)

**TEST 6-9**: New format parse validation
- Format detection (spoke key at root)
- Operator count (3 operators)
- OCP version normalization (major.minor → 4.22)
- Namespace field usage (namespace vs nsname)

### DUAL FORMAT COMPATIBILITY

**TEST 10-11**: Cross-format validation
- Both formats produce same operator count
- Both formats produce same OCP version

### GENERATE TESTS

**TEST 12-17**: Lockdown generation validation
- Lockdown file created
- Valid JSON structure (deployment, operators, metadata sections)
- Deployment section correct (no omit placeholders)
- Operators included (2 operators from metadata)
- Operator fields complete with digests (@sha256:)
- Metadata section correct (hub_name, build_number, mirror_timestamp)

## Mock Data

### Legacy Format Lockdown
Created at `/tmp/molecule-tests/spoke-lockdown-legacy.json`:
- 3 operators (sriov, ptp, local-storage)
- OCP version: 4.22
- Legacy lockdown structure

### New Format Lockdown
Created at `/tmp/molecule-tests/spoke-lockdown-new.json`:
- Same 3 operators
- Nested spoke.ocp structure
- split major/minor version fields
- namespace instead of nsname

### Mock Metadata
Pre-populated `lockdown_metadata_operators` dict:
- 2 operators with bundle + FBC digests
- Used for generate testing

## Expected Output

```
==========================================
  Lockdowns Role (Spoke) Tests: ALL PASSED
==========================================
✓ Legacy format parse: 5 tests passed
✓ New format parse: 4 tests passed
✓ Dual format compatibility: 2 tests passed
✓ Generate lockdown: 6 tests passed
==========================================
Total: 17 tests passed
==========================================
```

## What This Tests

**Parse Action (Dual Format)**:
1. Download lockdown JSON from URI (using `file://` for local testing)
2. Detect format (legacy vs new) automatically
3. Parse JSON and extract operators, OCP version, pull spec
4. Normalize output facts regardless of format

**Generate Action**:
1. Accept accumulated metadata from upstream mirroring hooks
2. Generate lockdown JSON matching legacy format
3. Use actual pull spec strings (not omit placeholders)
4. Include only operators with bundle digests
5. Add metadata section with hub name, build number, timestamp

## Continuous Integration

Add to CI pipeline:

```yaml
test-lockdowns-spoke:
  script:
    - cd playbooks/telco-kpis/roles/lockdowns
    - ansible-playbook -i localhost, -c local molecule/spoke/default/test.yml
```

## Related Files

- Role tasks:
  - `playbooks/telco-kpis/roles/lockdowns/tasks/spoke/parse.yml`
  - `playbooks/telco-kpis/roles/lockdowns/tasks/spoke/generate.yml`
  - `playbooks/telco-kpis/roles/lockdowns/tasks/spoke/accumulate-metadata-*.yml`
- Template: `playbooks/telco-kpis/roles/lockdowns/templates/spoke/lockdown-generate.json.j2`
- Wrapper playbook: `playbooks/telco-kpis/mirror-spoke-operators.yml`
- Common tasks: `playbooks/telco-kpis/roles/lockdowns/tasks/common/`

## Makefile Integration

Update `playbooks/telco-kpis/roles/lockdowns/Makefile` to include spoke tests:

```makefile
.PHONY: test-spoke
test-spoke:
	molecule test -s spoke

.PHONY: test-all
test-all: test-hub test-spoke
```
