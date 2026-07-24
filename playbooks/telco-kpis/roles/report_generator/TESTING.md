# Testing the Report Generator Role

## Overview

The report_generator role includes Molecule-based tests that run inside the eco-ci-cd container, ensuring all dependencies are resolved correctly.

## Running Tests

### Quick Test (Recommended)

```bash
cd playbooks/telco-kpis/roles/report_generator
make test
```

This command:
1. Runs in the `quay.io/telcov10n-ci/eco-ci-cd:latest` container
2. Executes all test phases: prepare → converge → verify
3. Validates report generation with mock data

### Test Output

Expected output:
```
==========================================
  Running Report Generator Tests
==========================================
[PLAY] Prepare test environment
  ✓ Created mock artifacts: oslat, cpu_util, ptp
  
[PLAY] Converge - Run report_generator role  
  ✓ Discovered 3 test runs
  ✓ Parsed node-info
  ✓ Parsed test results
  ✓ Generated markdown report
  
[PLAY] Verify - Check report output
  ✓ Report file exists
  ✓ Contains Test Summary
  ✓ Contains Cluster Configuration  
  ✓ Contains OSLAT section
  ✓ Contains CPU_UTIL section
  ✓ Test anchors use underscores (#oslat, #cpu_util)

✓ Report generator tests passed!
```

## Test Scenarios

### Test 1: Report File Creation
Verifies that `test-report.md` is created in the output directory.

### Test 2: Report Sections
Ensures all required sections are present:
- Test Summary table
- Cluster Configuration
- Test Results (per test type)
- Report Metadata

### Test 3: Test Name Normalization
Validates that test anchors use underscores:
- `#oslat` ✓ (not `#os-lat`)
- `#cpu_util` ✓ (not `#cpu-util`)
- `#ptp` ✓

### Test 4: Cluster Metadata
Checks that node-info data is correctly parsed:
- OCP Version: 4.14.0
- Kernel: 5.14.0-284.el9.x86_64
- Power Mode: performance
- BIOS/Microcode versions

### Test 5: Test Result Parsing
Validates OSLAT and CPU_UTIL parsers:
- JUnit XML parsing (tests/failures/skipped counts)
- Log file inclusion
- Key metrics display

### Test 6: Stubbed Parsers
Confirms stubbed parsers (PTP, etc.) return "N/A" without failing

## Test Data

### Mock Artifacts Created

```
/tmp/molecule-report-generator/
├── artifacts/
│   ├── node-info-test-spoke-01.json
│   ├── oslat-test-spoke-01-20260706-100000/
│   │   ├── oslat_suite_test.xml
│   │   └── podman-run.log
│   ├── cpu_util-test-spoke-01-20260706-120000/
│   │   ├── cpu_suite_test.xml
│   │   └── podman-run.log
│   └── ptp-test-spoke-01-20260706-130000/
│       └── podman-run.log
└── output/
    └── test-report.md
```

### OSLAT Mock Data
- **XML:** 13 tests, 0 failures, 0 skipped
- **Log:** "Max latency: 15us, All cores passed"
- **Expected Status:** PASS
- **Expected Metric:** P:13 F:0 S:0

### CPU_UTIL Mock Data
- **XML:** 2 tests, 0 failures, 11 skipped
- **Log:** "Baseline: 2.5%, Load: 85.3%"
- **Expected Status:** PASS
- **Expected Metric:** P:2 F:0 S:11

### PTP Mock Data
- **Parser:** Stubbed (not implemented)
- **Expected Status:** N/A
- **Expected Metric:** "Parser not implemented"

## Debugging Failed Tests

### View Detailed Output

```bash
cd playbooks/telco-kpis/roles/report_generator
make converge  # Run role with -vvv for debug
```

### Inspect Generated Report

```bash
cat /tmp/molecule-report-generator/output/test-report.md
```

### Check Artifact Discovery

```bash
ls -la /tmp/molecule-report-generator/artifacts/
```

### Run Individual Phases

```bash
make prepare   # Set up test data
make converge  # Run role
make verify    # Check assertions
```

## Integration with CI/CD

### Jenkins Pipeline Example

```groovy
stage('Test Report Generator Role') {
    steps {
        script {
            sh '''
                cd playbooks/telco-kpis/roles/report_generator
                make test
            '''
        }
    }
}
```

### GitHub Actions Example

```yaml
- name: Test report_generator role
  run: |
    cd playbooks/telco-kpis/roles/report_generator
    make test
```

## Cleanup

Remove test artifacts:

```bash
make clean
```

This removes `/tmp/molecule-report-generator/` directory.

## Adding New Test Cases

### 1. Update prepare.yml

Add mock data for new test type:

```yaml
- name: Create mock NEWTEST directory
  ansible.builtin.file:
    path: "{{ shared_artifact_dir }}/newtest-{{ spoke_cluster }}-20260706-140000"
    state: directory

- name: Create mock NEWTEST XML
  ansible.builtin.copy:
    content: |
      <?xml version="1.0" encoding="UTF-8"?>
      <testsuite tests="5" failures="0">...
    dest: "{{ shared_artifact_dir }}/newtest-{{ spoke_cluster }}-20260706-140000/result.xml"
```

### 2. Implement Parser

Create `tasks/parsers/parse_newtest.yml`

### 3. Update verify.yml

Add assertions for new test:

```yaml
- name: Verify NEWTEST section in report
  ansible.builtin.assert:
    that:
      - "'NEWTEST' in (report_content.content | b64decode)"
      - "'#newtest' in (report_content.content | b64decode)"
```

### 4. Run Tests

```bash
make test
```

## Troubleshooting

### Error: "No module named 'ansible'"

**Cause:** Running outside container without Ansible installed

**Solution:** Use `make test` instead of `molecule test`

### Error: "Could not find role 'report_generator'"

**Cause:** ANSIBLE_ROLES_PATH not set correctly

**Solution:** Run via Makefile which sets the path automatically

### Error: "Report file not found"

**Cause:** Role failed to generate report

**Solution:** Check converge output for errors in parsers

## Related Documentation

- [Role README](README.md) - Usage and architecture
- [Integration Guide](INTEGRATION.md) - Integration with generate-report.yml
- [Lockdowns Testing](../lockdowns/molecule/hub/README.md) - Similar test pattern
