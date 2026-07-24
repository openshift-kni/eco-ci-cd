# Integration with generate-report.yml

## Changes Made

### 1. Created `report_generator` Role

A complete Ansible role that replaces the Python script `analyze-podman-test-results.py`:

**Location:** `playbooks/telco-kpis/roles/report_generator/`

**Key Features:**
- Test name normalization (handles `cpu-util` and `cpu_util`)
- Modular parsers (one file per test type)
- Jinja2 templates for report generation
- Molecule unit tests
- No external dependencies (pure Ansible)

### 2. Updated `generate-report.yml`

**Removed:**
- Python script execution via podman container
- Test-runner image build requirement
- Complex volume mounting and container orchestration

**Added:**
- Simple role invocation with 3 variables:
  ```yaml
  - name: Generate report using report_generator role
    ansible.builtin.include_role:
      name: report_generator
    vars:
      output_dir: "{{ temp_output_dir.path }}"
      use_latest: true
      create_tarball: false
  ```

**Variables automatically passed from playbook context:**
- `spoke_cluster` - From Jenkins parameter
- `shared_artifact_dir` - From telco_kpis defaults
- `output_filename` - Generated in playbook
- `test_filter` - From Jenkins parameter (optional)

### 3. Fixed Test Name Consistency

**Problem:** Mismatch between Jenkins TEST_NAME (underscores) and directory names (hyphens)

**Solution:** Test type mapping in role defaults:
```yaml
report_generator_test_type_mapping:
  cpu-util: cpu_util
  cpu_util: cpu_util
  rds-compare: rds_compare
  rds_compare: rds_compare
```

**Result:** Both `cpu-util-spree-02-...` and `cpu_util-spree-02-...` directories work correctly

## Testing the Integration

### Run Molecule Tests

```bash
cd playbooks/telco-kpis/roles/report_generator
molecule test
```

### Test with Jenkins Job

1. Run `telco-kpis-generate-report` job
2. Parameters:
   - SPOKE_CLUSTER: spree-02
   - SKIP_REBUILD_IMAGE: true (no longer needed)
3. Check output report matches previous format

### Verify Report Format

Expected report sections:
- ✅ Test Summary table with `#cpu_util` anchors (not `#cpu-util`)
- ✅ Cluster Configuration
- ✅ Test Results (OSLAT, CPU_UTIL, etc.)
- ✅ Artifact links using underscores (`cpu_util/podman-run.log`)

## Benefits

### Maintainability
- **Before:** 2193-line Python script, hard to modify
- **After:** Modular parsers, ~50 lines each

### Testing
- **Before:** No unit tests
- **After:** Molecule tests for each parser

### Dependencies
- **Before:** Container build, Python script from GitLab
- **After:** Pure Ansible, no external dependencies

### Extensibility
- **Before:** Edit monolithic Python file
- **After:** Add new parser file + 3 lines config

## Migration Path

### Current State (After Integration)
- ✅ Role created and integrated
- ✅ OSLAT parser implemented
- ✅ CPU_UTIL parser implemented  
- ✅ Test name normalization working
- ⏳ Other test parsers stubbed (return N/A)

### Next Steps

1. **Test with real data** (immediate)
   - Run generate-report job
   - Verify report format matches

2. **Implement remaining parsers** (incremental)
   - PTP
   - Cyclictest
   - Reboot
   - RFC2544
   - RDS Compare
   - BIOS Validation
   - ZTP Deployment

3. **Remove Python script dependency** (when complete)
   - Update setup-test-runner.yml
   - Remove Python script clone from GitLab

## Rollback Plan

If issues arise, rollback is simple:

```yaml
# In generate-report.yml, replace:
- name: Generate report using report_generator role
  ansible.builtin.include_role:
    name: report_generator

# With original:
- name: Run analyze-podman-test-results.py in test-runner container
  ansible.builtin.shell: |
    podman run --rm \
      -v {{ shared_artifact_dir }}:/reports/podman-runs:ro,Z \
      -v {{ temp_output_dir.path }}:/workspace/output:rw,Z \
      telco-kpis-test-runner:latest \
      python3.11 /opt/analyze-podman-test-results.py {{ python_args }}
```

And restore:
```yaml
- name: Ensure test-runner container image exists on bastion
  ansible.builtin.import_tasks: tasks/setup-test-runner.yml
```

## Files Modified

1. `playbooks/telco-kpis/generate-report.yml`
   - Replaced Python script call with role
   - Removed test-runner setup

2. `playbooks/telco-kpis/tasks/run-cpu_util-test.yml`
   - Removed `test_artifact_name: "cpu-util"` override

3. `playbooks/telco-kpis/tasks/run-bios-validation-test.yml`
   - Changed to use `test_name` variable

4. `playbooks/telco-kpis/tasks/run-rds-compare-test.yml`
   - Changed to use `test_name` variable

5. `playbooks/telco-kpis/tasks/run-test.yml`
   - Removed `test_artifact_name` fallback pattern

## Files Created

- `playbooks/telco-kpis/roles/report_generator/` (complete role)
  - 21 files total
  - Parsers, templates, tests, documentation
