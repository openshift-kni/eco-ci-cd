# Report Generator Role

Generates Markdown test reports from Telco-KPIs test artifacts. Replaces the Python `analyze-podman-test-results.py` script with a pure Ansible implementation for better maintainability and testability.

## Features

- **Modular parsers**: Each test type has its own dedicated parser
- **Test name normalization**: Handles both `cpu-util` and `cpu_util` naming variants
- **Template-based**: Uses Jinja2 templates for easy customization
- **Timestamp filtering**: Automatically excludes tests older than node-info collection
- **No external dependencies**: Pure Ansible, no Python scripts
- **Molecule tested**: Unit tests for parsers and report generation

## Requirements

- Ansible 2.9+
- Test artifacts in standard directory format: `{test_name}-{spoke}-{YYYYMMDD}-{HHMMSS}/`
- `node-info-{spoke}.json` with `collected_at` timestamp (optional but recommended)

## How Timestamp Filtering Works

The role automatically filters test artifacts based on the `node-info-{spoke}.json` timestamp:

1. **When node-info exists**: Only includes tests with timestamps >= node-info `collected_at`
2. **Deletes old artifacts**: Removes tests older than node-info to save disk space
3. **Report action**: Sets `report_action=new` if old tests were excluded, `update` otherwise

This ensures reports only include tests from the **current environment configuration**.

**Example:**
```
node-info collected_at: 2026-07-03T12:00:00Z  →  timestamp: 20260703-120000

Artifacts:
  oslat-spree-02-20260703-100000    → EXCLUDED (10:00 < 12:00) ❌
  ptp-spree-02-20260703-123000      → INCLUDED (12:30 > 12:00) ✅
  cpu_util-spree-02-20260703-150000 → INCLUDED (15:00 > 12:00) ✅
```

## Role Variables

### Required Variables

```yaml
spoke_cluster: spree-02              # Spoke cluster name
shared_artifact_dir: /path/to/artifacts  # Directory containing test artifacts
output_filename: report.md           # Output report filename
output_dir: /path/to/output         # Output directory for report
```

### Optional Variables

```yaml
test_filter: "oslat,ptp"            # Comma-separated list of tests to include (default: all)
use_latest: true                     # Use only latest run per test type (default: true)
create_tarball: true                 # Create compressed tarball of artifacts (default: true)
tarball_name: artifacts.tar.gz       # Custom tarball name (default: auto-generated)
```

## Example Playbook

```yaml
- name: Generate test report
  hosts: bastion
  tasks:
    - name: Generate report
      ansible.builtin.include_role:
        name: report_generator
      vars:
        spoke_cluster: spree-02
        shared_artifact_dir: /home/telcov10n/telco-kpis-artifacts/spree-02
        output_filename: telco-kpis-report-spree-02-{{ ansible_date_time.date }}.md
        output_dir: /tmp/reports
```

## Test Parsers

### Implemented Parsers

- **oslat**: Parses JUnit XML and logs
- **cpu_util**: Parses JUnit XML and logs

### Stub Parsers (Pending Implementation)

- ptp
- cyclictest
- reboot
- rfc2544
- rds_compare
- bios_validation
- ztp_ai_deployment_time

## Adding New Test Types

1. Add test name mapping in `defaults/main.yml`:
   ```yaml
   report_generator_test_type_mapping:
     my-new-test: my_new_test
     my_new_test: my_new_test
   ```

2. Create parser in `tasks/parsers/parse_my_new_test.yml`

3. Add parser mapping:
   ```yaml
   report_generator_parsers:
     my_new_test: parse_my_new_test.yml
   ```

4. Add to test order for report generation:
   ```yaml
   report_generator_test_order:
     - my_new_test
   ```

## Testing

### Run Molecule Tests (Recommended - in container)

```bash
cd playbooks/telco-kpis/roles/report_generator
make test
```

This runs tests inside the `eco-ci-cd` container with all dependencies resolved.

### Run Individual Test Phases (Local Ansible)

```bash
cd playbooks/telco-kpis/roles/report_generator
make prepare   # Create mock artifacts
make converge  # Run role
make verify    # Validate output
```

**Note:** Individual phases require local Ansible installation.

## Architecture

```
report_generator/
├── defaults/main.yml          # Default variables and test mappings
├── tasks/
│   ├── main.yml              # Main entry point
│   ├── discover_artifacts.yml # Find and normalize test directories
│   ├── parse_node_info.yml   # Parse cluster metadata
│   ├── parse_test.yml        # Route to test-specific parser
│   ├── generate_markdown.yml # Generate report from template
│   ├── create_tarball.yml    # Compress artifacts
│   └── parsers/              # Test-specific parsers
│       ├── parse_oslat.yml
│       ├── parse_cpu_util.yml
│       └── ...
├── templates/
│   └── report.md.j2          # Main report template
└── molecule/                 # Unit tests
    └── default/
        ├── molecule.yml
        ├── converge.yml
        └── verify.yml
```

## Migration from Python Script

The role replaces `analyze-podman-test-results.py` with equivalent Ansible logic:

- **Test discovery**: `discover_artifacts.yml` replaces directory scanning
- **Test parsing**: Individual parsers replace monolithic parsing functions
- **Report generation**: Jinja2 template replaces string concatenation
- **Test name normalization**: Mapping dict handles both hyphen/underscore variants

## License

Same as eco-ci-cd repository
