# Gitea Role for Telco KPIs Report Publishing

Ansible role for deploying Gitea on bastion hosts and publishing Telco KPIs test reports to a Git repository.

## Features

- **Automated Gitea Deployment**: Deploy Gitea as a rootless podman container on bastion
- **Vault-Based Authentication**: Uses bastion credentials from HashiCorp Vault
- **Repository Management**: Auto-creates `telco-kpis-reports` repository
- **Report Publishing**: Publishes test reports with artifacts to Git
- **Markdown Index**: Maintains top-level README.md with links to all reports sorted by date
- **Environment-Aware Reporting**: Timestamp-based filtering excludes old tests when environment changes
- **Retention Policy**: Configurable report retention (default: keep last 7 days)

## Architecture

```
Bastion Host (telco-kpis-prow-kni-qe-71-bastion)
├── Gitea Container (rootless podman)
│   ├── HTTP: http://bastion.kni-qe-71.telco-kpis.rdu3.redhat.com:3000/
│   ├── SSH: ssh://git@bastion.kni-qe-71.telco-kpis.rdu3.redhat.com:2222/
│   └── Database: SQLite3 (/data/gitea/gitea.db)
│
├── Data Directory: ~/gitea/data/
│   ├── gitea/conf/app.ini (configuration)
│   ├── git/repositories/ (Git repos)
│   └── gitea/log/ (logs)
│
└── Repository: telco-kpis-reports
    ├── README.md (index of all reports)
    └── reports/
        └── YYYY-MM-DD/
            └── <spoke-cluster>/
                ├── <report-name>.md
                ├── oslat/
                ├── ptp/
                ├── cyclictest/
                ├── cpu-util/
                ├── reboot/
                ├── rfc2544/
                ├── rds-compare/
                └── node-info-<spoke>.json
```

## Vault Integration

### Admin Credentials

The role uses **bastion credentials from HashiCorp Vault** instead of hardcoded passwords:

```yaml
# Vault variables (automatically provided by getVaults() in Jenkins)
gitea_admin_user: "{{ ansible_user }}"           # From bastion vault
gitea_admin_password: "{{ ansible_password }}"   # From bastion vault
gitea_admin_email: "{{ gitea_admin_user }}@localhost"
```

**Vault Sources** (priority order):
1. Bastion `host_vars` vault (e.g., `telco-kpis-prow-kni-qe-71-bastion`)
2. `ansible_group_bastions` vault
3. `ansible_group_all` vault

**Expected Vault Variables**:
- `ansible_user`: Bastion username (typically `telcov10n`)
- `ansible_password`: Bastion user password

### Fallback Behavior

If vault credentials are not available, the role will:
1. Check `BASTION_PASSWORD` environment variable
2. Fail with detailed error message indicating vault configuration issue

## Usage

### Basic Usage (Jenkins Job)

```groovy
// In Jenkinsfile
stage('Generate Report') {
    steps {
        script {
            def extraVarsList = [
                "spoke_cluster=spree-02",
                "output_filename=report.md",
                "timestamp=${TIMESTAMP}",
                "development_mode=true"  // Enable Gitea publishing
            ]

            runAnsiblePlaybook(
                playbookName: "generate-report.yml",
                playbookPath: "playbooks/telco-kpis",
                inventoryPath: "inventories/ocp-deployment/build-inventory.py",
                volumeName: PODMAN_VOLUME_NAME,
                artifactFolder: true,
                extraVars: extraVarsList
            )
        }
    }
}
```

### Direct Ansible Usage

```bash
# With vault credentials
ansible-playbook playbooks/telco-kpis/generate-report.yml \
  -i inventories/ocp-deployment/build-inventory.py \
  -e spoke_cluster=spree-02 \
  -e output_filename=report.md \
  -e timestamp=$(date +%Y%m%d-%H%M%S) \
  -e development_mode=true

# Override credentials (for testing)
ansible-playbook playbooks/telco-kpis/generate-report.yml \
  -i inventories/ocp-deployment/build-inventory.py \
  -e spoke_cluster=spree-02 \
  -e development_mode=true \
  -e gitea_admin_user=admin \
  -e gitea_admin_password=mypassword
```

## Report Action Logic

The role supports two modes of report publishing based on whether the environment configuration has changed:

### UPDATE Mode (Environment Stable)

**When**: No tests were excluded during report generation (`report_action: "update"`)

**Behavior**:
- Removes existing reports for today's date before publishing
- Assumes all test results belong to the same environment configuration
- Example: Re-running tests to gather more data without changing BIOS/PerfProfile

**Workflow**:
1. Find existing reports: `reports/2026-04-28/spree-02/telco-kpis-report-*.md`
2. Delete found reports
3. Publish new report with same date
4. README shows only latest report for today

### NEW Mode (Environment Changed)

**When**: Tests were excluded during report generation (`report_action: "new"`)

**Behavior**:
- Keeps all existing reports (preserves historical data for different configurations)
- Adds new report alongside previous ones
- Each report represents a distinct environment configuration

**Workflow**:
1. Skip deletion of existing reports
2. Publish new report with unique timestamp
3. README lists all reports sorted by date (newest first)

### Timestamp-Based Filtering (Upstream)

**Note**: The `report_action` variable is determined by the `generate-report.yml` playbook, not by this role.

**How It Works**:
1. **collect-node-info** captures environment state (BIOS, PerfProfile, etc.) with UTC timestamp
2. **Tests run** after collect-node-info, artifacts saved with UTC timestamps
3. **generate-report** compares test timestamps vs node-info timestamp:
   - Tests older than node-info → EXCLUDED (belong to previous environment)
   - Tests newer than node-info → INCLUDED (belong to current environment)
4. If tests excluded → `report_action: "new"` (environment changed)
5. If no tests excluded → `report_action: "update"` (environment stable)

**Critical**: Timestamps must be in same timezone (UTC) for accurate comparison:
- Test directories: `{test}-{spoke}-YYYYMMDD-HHMMSS` (UTC from eco-ci-cd container)
- Node-info: ISO8601 UTC format (e.g., `2026-04-28T15:48:45Z`)
- Conversion: `date -u -d "{iso8601}" +%Y%m%d-%H%M%S` (maintains UTC, not local time)

**Example Workflow**:
```bash
# Day 1: Initial baseline
collect-node-info (10:00 UTC) → oslat (10:30 UTC), ptp (11:00 UTC) → generate-report
# Result: report-1 with oslat + ptp

# Day 1: Change BIOS settings
collect-node-info (14:00 UTC) → cyclictest (14:30 UTC) → generate-report
# Filtering: oslat (10:30 < 14:00) EXCLUDED, ptp (11:00 < 14:00) EXCLUDED, cyclictest (14:30 > 14:00) INCLUDED
# Result: report-2 with cyclictest only, report-1 preserved
```

## Retention Policy

The role automatically removes old reports to prevent unlimited growth:

**Default**: Keep last 7 days (configurable via `gitea_report_retention_days`)

**How It Works**:
1. Find all date directories in `reports/`
2. Sort by date descending
3. Keep first N directories (N = `gitea_report_retention_days`)
4. Delete remaining directories

**Override**:
```yaml
# Keep last 14 days
gitea_report_retention_days: 14

# Disable retention (keep all reports)
gitea_report_retention_days: 0
```

## Role Variables

### Required Variables (from playbook)

| Variable | Description | Example |
|----------|-------------|---------|
| `spoke_cluster` | Spoke cluster name | `spree-02` |
| `report_file` | Markdown report filename | `telco-kpis-report-spree-02-20260427.md` |
| `report_tarball` | Artifacts tarball filename | `spree-02-artifacts-20260427-101530.tar.gz` |
| `report_action` | Report publishing mode | `new` or `update` |
| `development_mode` | Enable Gitea publishing | `true` |

### Default Variables (can be overridden)

| Variable | Default | Description |
|----------|---------|-------------|
| `gitea_container_name` | `gitea` | Podman container name |
| `gitea_http_port` | `3000` | HTTP port for Gitea web UI |
| `gitea_ssh_port` | `2222` | SSH port for Git operations |
| `gitea_domain` | `bastion.kni-qe-71.telco-kpis.rdu3.redhat.com` | Gitea domain |
| `gitea_admin_user` | `{{ ansible_user }}` | Admin username (from vault) |
| `gitea_admin_password` | `{{ ansible_password }}` | Admin password (from vault) |
| `gitea_repo_name` | `telco-kpis-reports` | Repository name |
| `gitea_image` | `docker.io/gitea/gitea:latest` | Gitea container image |
| `gitea_report_retention_days` | `7` | Keep reports for last N days (0 = keep all) |

## Tasks

### deploy.yml
- Checks if Gitea container exists
- Configures firewall rules (opens ports 3000/tcp and 2222/tcp)
- Creates data directory
- Deploys Gitea container with rootless podman
- Waits for Gitea to become accessible

### initialize.yml
- Checks installation status (INSTALL_LOCK)
- Completes installation via web API
- Creates admin user
- Generates API token for automation

### create-repository.yml
- Checks if `telco-kpis-reports` repository exists
- Creates repository with initial README
- Returns clone URLs (HTTP and SSH)

### publish-report.yml
- Clones repository to temporary directory
- Handles report action based on `report_action` variable:
  - **UPDATE**: Environment stable - Remove existing reports for today before publishing
  - **NEW**: Environment changed - Keep all historical reports, add new report alongside
- Creates dated directory structure: `reports/YYYY-MM-DD/<spoke>/`
- Copies Markdown report
- Extracts artifacts tarball
- Renames artifact directories to remove timestamps (e.g., `oslat-spree-02-20260428-110330/` → `oslat/`)
- Keeps only latest run per test type
- Fixes Markdown links to point to extracted artifacts
- Applies retention policy (deletes reports older than `gitea_report_retention_days`)
- Updates top-level README.md index
- Commits and pushes changes

### validate-credentials.yml
- Validates `ansible_user` is set
- Validates `ansible_password` is set
- Provides helpful error messages if vault credentials missing

## Examples

### Jenkins Job Parameter

```groovy
booleanParam {
    name('DEVELOPMENT_MODE')
    defaultValue(false)
    description('Enable Gitea publishing: Deploy Gitea (if needed) and publish report')
}
```

### Report Directory Structure

After publishing, the repository contains:

```
telco-kpis-reports/
├── README.md                           # Auto-generated index
└── reports/
    ├── 2026-04-27/
    │   ├── spree-01/
    │   │   ├── telco-kpis-report-spree-01-20260427-090530.md
    │   │   ├── oslat/
    │   │   │   ├── oslat0_logs
    │   │   │   ├── oslat_report.xml
    │   │   │   └── podman-run.log
    │   │   ├── ptp/
    │   │   ├── cyclictest/
    │   │   └── ...
    │   └── spree-02/
    │       └── ...
    └── 2026-04-26/
        └── ...
```

### Accessing Published Reports

**Web UI**: http://bastion.kni-qe-71.telco-kpis.rdu3.redhat.com:3000/telcov10n/telco-kpis-reports

**Git Clone**:
```bash
# HTTPS (requires credentials)
git clone http://bastion.kni-qe-71.telco-kpis.rdu3.redhat.com:3000/telcov10n/telco-kpis-reports.git

# SSH (requires SSH key)
git clone ssh://git@bastion.kni-qe-71.telco-kpis.rdu3.redhat.com:2222/telcov10n/telco-kpis-reports.git
```

## Troubleshooting

### Issue: Cannot access Gitea web UI (connection refused)

**Symptom**: `curl: (7) Failed to connect to bastion...:3000: Connection refused`

**Solution**: Ensure firewall ports are open:
```bash
# Check firewall rules
sudo firewall-cmd --list-ports

# Manually add rules if needed
sudo firewall-cmd --add-port=3000/tcp --permanent
sudo firewall-cmd --add-port=2222/tcp --permanent
sudo firewall-cmd --reload
```

**Note**: The role automatically configures firewall rules during deployment if firewalld is active.

### Issue: Gitea admin password not found

**Error**:
```
FAILED! => Gitea admin password not found in vault.
Expected vault variable: 'ansible_password' from bastion vault.
```

**Solution**:
1. Verify bastion vault contains `ansible_password`
2. Check vault path: `telcov10n-ci/teams/telco-kpis/bastions/telco-kpis-prow-kni-qe-71-bastion`
3. Ensure `getVaults()` retrieved bastion vault in Jenkins stage
4. Temporarily override with `-e gitea_admin_password=...` for testing

### Issue: Gitea container already exists

**Symptom**: Role fails because container already running

**Solution**: Role is idempotent - it skips deployment if container exists. To redeploy:
```bash
podman stop gitea && podman rm gitea
sudo rm -rf ~/gitea/data
```

### Issue: Git push fails with authentication error

**Symptom**: `fatal: Authentication failed`

**Solution**: Check credentials in clone URL:
```yaml
# Correct format (credentials embedded)
gitea_repo_http_url: "http://{{ gitea_admin_user }}:{{ gitea_admin_password }}@{{ gitea_domain }}:{{ gitea_http_port }}/{{ gitea_admin_user }}/{{ gitea_repo_name }}.git"
```

### Issue: Markdown links broken in published report

**Symptom**: Links to artifacts return 404

**Cause**: Report references `<report>.md.artifacts/` but role extracts to root

**Solution**: Role automatically fixes links with regex replace:
```yaml
regexp: '{{ report_file }}\.artifacts/'
replace: ''
```

### Issue: Report action always "update" even after environment change

**Symptom**: Multiple reports not showing up, only latest report visible

**Cause**: Timezone mismatch in timestamp comparison upstream in `generate-report.yml`

**Root Cause**:
- Test directory timestamps are in UTC: `oslat-spree-02-20260428-144048`
- Node-info timestamp is ISO8601 UTC: `2026-04-28T15:48:45Z`
- Conversion using `date -d` (without `-u`) converts to local time
- String comparison fails: `"144048" (UTC) > "114845" (EDT)` → incorrect result

**Solution**: Ensure `generate-report.yml` uses `date -u -d` to maintain UTC:
```yaml
- name: Convert node-info UTC timestamp to UTC YYYYMMDD-HHMMSS format
  ansible.builtin.shell: |
    date -u -d "{{ node_info_collected_at_utc.stdout }}" +%Y%m%d-%H%M%S
  register: node_info_utc_ts
```

**Verification**:
```bash
# Check if timestamps match timezone
ssh bastion "ls -l /home/telcov10n/telco-kpis-artifacts/spree-02/"
# Compare with node-info timestamp
ssh bastion "jq -r '.collected_at' /home/telcov10n/telco-kpis-artifacts/spree-02/node-info-spree-02.json"
```

**Git Commit**: `48e7606` (2026-04-28) - Critical timezone fix

## Security Considerations

1. **Vault-Based Credentials**: Never hardcode passwords - always use vault
2. **HTTP (not HTTPS)**: Current setup uses HTTP - Gitea is internal-only on bastion
3. **Embedded Credentials in Clone URL**: Credentials are embedded in Git remote URL during clone/push (temporary, in memory only)
4. **Podman Rootless**: Gitea runs as rootless container for isolation
5. **Auto-Cleanup**: Temporary git work directory is removed after publishing

## Future Enhancements

- [ ] Support HTTPS with self-signed certificates
- [ ] Use Git SSH authentication instead of HTTPS with embedded credentials
- [ ] Add webhook support for external notifications
- [ ] Support multiple bastions with separate Gitea instances
- [ ] Backup and restore functionality for Gitea data
- [ ] Integration with Red Hat SSO for authentication

## References

- **Gitea Documentation**: https://docs.gitea.io/
- **Gitea API**: https://docs.gitea.io/en-us/api-usage/
- **Your Prow Gitea Steps**: `~/repos/ztp-left-shifting/openshift-ci-dev/openshift/ccardeno-fork-release/ci-operator/step-registry/telcov10n/metal-single-node-spoke/gitea/`
