# Lockdowns Role

Unified Ansible role for hub and spoke operator lockdown management.

## Overview

This role provides a flexible interface for operator lockdown operations across hub and spoke clusters:

- **Parse Lockdown**: Download and parse lockdown JSON from URI, set facts for operator deployment
- **Capture Lockdown**: Query cluster state and generate lockdown JSON for reproducibility
- **Common Utilities**: Shared tasks for download, validation, and Gitea symlink generation

## Features

✅ **Unified Structure**: Single role for both hub and spoke lockdown operations  
✅ **Flexible Interface**: Mode + Action pattern for clean task dispatching  
✅ **Code Reuse**: Common tasks shared between hub and spoke  
✅ **Testable**: Molecule tests for both hub and spoke scenarios  

## Usage

### Parse Hub Lockdown

```yaml
- name: Parse hub lockdown from URI
  ansible.builtin.include_role:
    name: lockdowns
  vars:
    lockdown_mode: hub
    lockdown_action: parse
    hub_lockdown_uri: "https://gitea.example.com/lockdowns/hub-lockdown-dev-kpi-01.json"
```

**Sets facts:**
- `hub_lockdown_operators` - List of operators ready for deploy-ocp-operators.yml
- `hub_ocp_pull_spec` - OCP pull spec from lockdown
- `hub_ocp_version` - OCP version (major.minor format)

### Capture Hub Lockdown

```yaml
- name: Capture hub lockdown from cluster
  ansible.builtin.include_role:
    name: lockdowns
  vars:
    lockdown_mode: hub
    lockdown_action: capture
    kubeconfig: /tmp/hub-kubeconfig
    hub_cluster: dev-kpi-01
    hub_lockdown_output_file: /artifacts/hub-lockdown-dev-kpi-01-{{ ansible_date_time.epoch }}.json
```

**What it does:**
- Queries hub cluster using `kubernetes.core.k8s_info` for:
  - ClusterVersion (OCP pull spec, version, architecture via skopeo)
  - Subscriptions (operator details: name, namespace, catalog, channel, CSV)
  - OperatorGroups (operator group specs and targetNamespaces)
- Maps mirrored catalog names to upstream names:
  - `cs-redhat-operator-index-*` → `redhat-operators`
  - `cs-certified-operator-index-*` → `certified-operators`
  - `cs-community-operator-index-*` → `community-operators`
  - FBC catalogs (e.g., `topology-aware-lifecycle-manager-fbc`) → unchanged
- Generates lockdown JSON from template at `hub_lockdown_output_file`

**Sets facts:**
- `hub_lockdown_operators` - Captured operator list (with mapped catalog names)
- `hub_ocp_pull_spec` - OCP pull spec
- `hub_ocp_version` - OCP major.minor version
- `hub_ocp_full_version` - Full OCP version
- `hub_ocp_architecture` - Detected architecture (x86_64 or arm64)

### Parse Spoke Lockdown

```yaml
- name: Parse spoke lockdown from URI
  ansible.builtin.include_role:
    name: lockdowns
  vars:
    lockdown_mode: spoke
    lockdown_action: parse
    spoke_lockdown_uri: "https://gitea.example.com/lockdowns/spoke-lockdown-spree-02.json"
```

**Sets facts:**
- `spoke_lockdown_operators` - List of operators ready for deployment
- `spoke_ocp_pull_spec` - OCP pull spec from lockdown
- `spoke_ocp_version` - OCP version (major.minor format)

### Capture Spoke Lockdown

```yaml
- name: Capture spoke lockdown from cluster
  ansible.builtin.include_role:
    name: lockdowns
  vars:
    lockdown_mode: spoke
    lockdown_action: capture
    kubeconfig: /tmp/spoke-kubeconfig
    spoke_cluster: spree-02
    spoke_lockdown_output_file: /artifacts/spoke-lockdown-spree-02-{{ ansible_date_time.epoch }}.json
```

## Directory Structure

```
lockdowns/
├── tasks/
│   ├── main.yml                    # Entry point - dispatcher
│   ├── common/
│   │   ├── download-lockdown.yml   # Download from URI
│   │   ├── validate-structure.yml  # JSON validation
│   │   └── generate-symlink.yml    # Gitea symlink creation
│   ├── hub/
│   │   ├── parse.yml              # Parse hub lockdown
│   │   └── capture.yml            # Capture hub lockdown
│   └── spoke/
│       ├── parse.yml              # Parse spoke lockdown
│       └── capture.yml            # Capture spoke lockdown
├── templates/
│   ├── hub/
│   │   └── lockdown.json.j2       # Hub lockdown JSON template
│   └── spoke/
│       └── lockdown.json.j2       # Spoke lockdown JSON template
├── molecule/
│   ├── hub/                       # Hub lockdown tests
│   │   └── default/
│   └── spoke/                     # Spoke lockdown tests
│       └── default/
└── README.md
```

## Lockdown JSON Format

### Hub Lockdown

```json
{
  "hub": {
    "ocp": {
      "pull_spec": "quay.io/openshift-release-dev/ocp-release:4.21.20-x86_64",
      "major_version": "4",
      "minor_version": "21",
      "full_version": "4.21.20",
      "architecture": "x86_64"
    },
    "operators": [
      {
        "name": "advanced-cluster-management",
        "namespace": "open-cluster-management",
        "catalog": "redhat-operators",
        "channel": "release-2.15",
        "subscription_name": "...",
        "installed_csv": "...",
        "install_plan_approval": "Automatic",
        "og_name": "...",
        "og_spec": {}
      }
    ],
    "metadata": {
      "cluster_name": "dev-kpi-01",
      "capture_timestamp": "2026-06-19T14:30:00Z"
    }
  }
}
```

### Spoke Lockdown

```json
{
  "spoke": {
    "ocp": {
      "pull_spec": "quay.io/openshift-release-dev/ocp-release:4.21.20-x86_64",
      "major_version": "4",
      "minor_version": "21",
      "full_version": "4.21.20",
      "architecture": "x86_64"
    },
    "operators": [
      {
        "name": "sriov-network-operator",
        "namespace": "openshift-sriov-network-operator",
        "catalog": "redhat-operators",
        "channel": "stable",
        "subscription_name": "...",
        "installed_csv": "...",
        "install_plan_approval": "Automatic",
        "og_name": "...",
        "og_spec": {}
      }
    ],
    "metadata": {
      "cluster_name": "spree-02",
      "capture_timestamp": "2026-06-19T14:30:00Z"
    }
  }
}
```

## Design Decisions: Repeatability vs Flexibility

### Hub Lockdowns: Catalog Channel Mutability

**Problem**: OLM operator channels are **mutable** - the same channel (e.g., `stable-2.10`) can point to different CSV versions over time as Red Hat releases updates.

**Example failure scenario:**
1. **Capture time** (Day 1): Channel `stable-2.10` → `multicluster-engine.v2.10.3`
2. Lockdown JSON saved with `"installed_csv": "multicluster-engine.v2.10.3"`
3. **Deployment time** (Day 30): Channel `stable-2.10` → `multicluster-engine.v2.11.2` (channel updated)
4. Operator deployment creates Subscription → InstallPlan with CSV `v2.11.2`
5. Upstream role waits for InstallPlan with CSV `v2.10.3` → **timeout failure**

**Root cause**: The `redhatci.ocp.olm_operator` role (used by `ocp_operator_deployment`) waits for an InstallPlan containing the exact `installed_csv` value. When channels drift to newer versions, this wait condition never succeeds.

**Solution**: **Remove `installed_csv` from hub lockdown JSON**

**Rationale for hubs:**
- Hub clusters are **administrative infrastructure**, not production workloads
- Hub configuration can tolerate minor version drift within the same channel
- Newer patch versions (e.g., v2.11.2 vs v2.10.3) typically maintain API compatibility
- Channels represent semantic versioning boundaries (stable-2.10 vs stable-2.11)
- Failing deployments due to stale CSV versions is worse than accepting newer patches

**What gets captured instead:**
```json
{
  "name": "multicluster-engine",
  "namespace": "multicluster-engine",
  "catalog": "redhat-operators",
  "channel": "stable-2.10",
  "subscription_name": "multicluster-engine",
  "install_plan_approval": "Automatic",
  "og_name": "multicluster-engine",
  "og_spec": {"targetNamespaces": ["multicluster-engine"]}
}
```

This allows OLM to resolve to whatever CSV the channel currently points to, ensuring deployments succeed even when channels are updated.

### Spoke Lockdowns: Strict Repeatability (Future Consideration)

**Different requirements:**
- Spoke clusters run **production Telco workloads** (CNFs, RAN functions)
- Configuration must be **bit-for-bit identical** across spoke deployments
- Testing requires **exact reproducibility** for valid comparisons
- Any version drift could invalidate performance benchmarks or compliance tests

**Challenge**: How to achieve strict repeatability when channels are mutable?

**Option 1: Mirrored catalogs** (Current approach for disconnected environments)
- When operators are mirrored to internal registry, catalog state is **frozen** at mirror time
- `ocp_operator_mirror` role creates `ImageSetConfiguration` with specific catalog versions
- Generated `ImageDigestMirrorSet` (IDMS) and `CatalogSource` manifests pin exact images
- Subsequent deployments use these mirrored catalogs, not live upstream channels
- **Result**: Channel state is immutable - `stable-2.10` always resolves to the same CSV

**Option 2: Capture CatalogSource images** (Not currently implemented)
- Capture `CatalogSource.spec.image` (e.g., `registry.redhat.io/redhat/redhat-operator-index:v4.21`)
- Store in lockdown JSON and override upstream catalog image construction
- **Challenge**: Upstream `deploy-ocp-operators.yml` constructs catalog images from OCP version
- Would require patching upstream or providing catalog images per-operator

**Option 3: Pin CSV in Subscription** (Requires upstream role changes)
- Use `spec.startingCSV` in Subscription to force exact version
- OLM will install exactly that CSV regardless of channel state
- **Challenge**: `redhatci.ocp.olm_operator` role doesn't support this parameter
- Would require contribution to upstream collection

**Current spoke approach**: 
- Disconnected deployments use mirrored catalogs (Option 1) → **strict repeatability achieved**
- Connected deployments use live catalogs → **accept channel drift** (same as hubs)
- If strict repeatability needed for connected spokes, implement Option 2 or 3

### Why Not Capture Catalog Images?

**Investigation finding** (2026-06-22): The oc-mirror binary version (e.g., 4.22) does **not** override catalog selection.

**What actually happens:**
1. Lockdown sets `version: "4.21"` → `ocp_operator_mirror_version: "4.21"`
2. Upstream correctly constructs `registry.redhat.io/redhat/redhat-operator-index:v4.21`
3. `ImageSetConfiguration` explicitly specifies this catalog
4. oc-mirror (regardless of binary version) uses the catalog from `ImageSetConfiguration`

**Therefore**: Capturing catalog images would not solve the channel mutability problem. The issue is not which catalog version is used, but that **catalog channels change over time** even for the same catalog image tag.

### Summary

| Cluster Type | Repeatability Requirement | `installed_csv` Field | Channel Drift Handling |
|--------------|---------------------------|----------------------|------------------------|
| **Hub** | Flexible (administrative infra) | ❌ Removed | Accept newer versions in same channel |
| **Spoke (Disconnected)** | Strict (production workloads) | ❌ Not needed | Mirrored catalogs freeze channel state |
| **Spoke (Connected)** | Best-effort | ❌ Not needed | Accept channel drift (same as hubs) |

**Related bugs/issues:**
- Build #89 failure: InstallPlan timeout waiting for CSV `v2.10.3` when channel resolved to `v2.11.2`
- Commits: cf8a8aa (hub lockdown feature), 69f5c12 (FBC metadata enrichment)

## Testing

Each mode (hub/spoke) has its own Molecule test suite:

```bash
# Test hub lockdown
cd playbooks/telco-kpis/roles/lockdowns
molecule test -s hub

# Test spoke lockdown
molecule test -s spoke
```

## Common Tasks

### download-lockdown.yml

Downloads lockdown JSON from URI to local path.

**Variables:**
- `lockdown_uri` (required) - URL to lockdown JSON
- `lockdown_download_path` (optional) - Local save path (default: /tmp/lockdown.json)

### validate-structure.yml

Validates lockdown JSON structure for hub or spoke.

**Variables:**
- `lockdown_data` (required) - Parsed JSON dictionary
- `lockdown_mode` (required) - 'hub' or 'spoke'

### generate-symlink.yml

Creates symlink for latest lockdown (Gitea integration).

**Variables:**
- `lockdown_output_file` (required) - Path to generated lockdown
- `lockdown_mode` (required) - 'hub' or 'spoke'

**Creates:** `{mode}-lockdown-latest.json` symlink

## Integration with deploy-ocp-operators.yml

The `playbooks/telco-kpis/deploy-ocp-operators.yml` wrapper uses this role to:

1. **Parse lockdown** (if `hub_lockdown_uri` provided)
2. **Call upstream** `playbooks/deploy-ocp-operators.yml` with transformed operators
3. **Capture lockdown** (if `generate_hub_lockdown` requested)

See `playbooks/telco-kpis/deploy-ocp-operators.yml` for integration example.

## Development Status

- ✅ Role structure created
- ✅ Common tasks implemented (download, validate, symlink)
- ✅ Hub parse task implemented and tested (10 passing tests)
- ✅ Hub capture task implemented (ported from deprecated branch)
- ✅ Spoke parse task implemented
- ⏳ Spoke capture task (TODO: implement)
- ⏳ Spoke molecule tests (TODO: create)
- ✅ Hub molecule tests (parse action validated)

## Legacy Code Access for Reuse

### Where to Find Legacy Implementation

The original lockdown implementation (before unified role refactoring) is preserved in the branch:
```
ipa-telco-kpis-prow-migration-20260619-before-deploy-ocp-operators-untouched
```

**Legacy Roles Location:**
```
playbooks/telco-kpis/roles/
├── lockdown_config/              # Legacy parsing and download logic
│   ├── tasks/
│   │   ├── parse_hub_lockdown.yml
│   │   ├── parse_spoke_lockdown.yml
│   │   ├── resolve_gitlab_symlinks.yml    # ⭐ GitLab symlink resolver
│   │   └── main.yml
│   └── templates/
│       └── resolve_gitlab_symlinks.sh.j2   # ⭐ Symlink resolution script
├── hub_lockdown_capture/         # Legacy hub capture logic
│   ├── tasks/main.yml
│   └── templates/hub-lockdown.json.j2
└── spoke_operator_lockdown/      # Legacy spoke capture logic
    ├── tasks/main.yml
    └── templates/lockdown-spoke.json.j2
```

### How to Access Legacy Code

```bash
# View legacy file
git show ipa-telco-kpis-prow-migration-20260619-before-deploy-ocp-operators-untouched:playbooks/telco-kpis/roles/lockdown_config/tasks/resolve_gitlab_symlinks.yml

# View legacy template
git show ipa-telco-kpis-prow-migration-20260619-before-deploy-ocp-operators-untouched:playbooks/telco-kpis/roles/lockdown_config/templates/resolve_gitlab_symlinks.sh.j2

# List all files in legacy role
git ls-tree -r --name-only ipa-telco-kpis-prow-migration-20260619-before-deploy-ocp-operators-untouched playbooks/telco-kpis/roles/lockdown_config/
```

### How to Adapt Legacy Code to Unified Role

**Example: GitLab Symlink Resolver (ported in commit b39f200)**

**Legacy location:**
- `playbooks/telco-kpis/roles/lockdown_config/templates/resolve_gitlab_symlinks.sh.j2`

**New location:**
- `playbooks/telco-kpis/roles/lockdowns/templates/resolve-gitlab-symlinks.sh.j2`

**Key adaptations:**
1. **Variable Renaming:**
   ```diff
   - INITIAL_URL="{{ lockdown_url }}"
   - DEST_FILE="{{ lockdown_dest }}"
   + INITIAL_URL="{{ lockdown_uri }}"
   + DEST_FILE="{{ lockdown_download_path }}"
   ```

2. **Integration Point:**
   - **Legacy**: Called from `lockdown_config/tasks/resolve_gitlab_symlinks.yml`
   - **New**: Called from `lockdowns/tasks/common/download-lockdown.yml`

3. **Naming Convention:**
   - **Legacy**: Used underscores (`resolve_gitlab_symlinks.sh.j2`)
   - **New**: Use hyphens for consistency (`resolve-gitlab-symlinks.sh.j2`)

**Why this pattern works:**
- GitLab's `/-/raw/` endpoint returns symlink content as text, not the target file
- The resolver script detects JSON vs symlink text and recursively follows chains
- Handles relative paths (`../`, `./`), absolute paths, and multi-hop resolution
- Reusable pattern: download → detect → resolve → save

**Commits demonstrating adaptation:**
- `b39f200` - Add GitLab symlink resolver for lockdown downloads
- `9ad2ceb` - Revert slurp approach (shows why legacy approach was needed)

### When to Reference Legacy Code

**✅ Reuse when:**
- Porting specialized logic (GitLab symlink resolution, catalog name mapping)
- Finding tested patterns for Kubernetes resource queries
- Understanding historical context for design decisions

**❌ Don't copy blindly:**
- Legacy code had role-specific naming (`hub_lockdown_*` vs `lockdown_*`)
- Legacy had duplication across hub/spoke roles (unified role eliminates this)
- Legacy used different file organization (flat vs common/hub/spoke structure)

**Migration checklist:**
1. Identify legacy file with `git show <branch>:<path>`
2. Extract reusable logic (scripts, queries, transformations)
3. Adapt variable names to unified role conventions
4. Place in appropriate location (common/ vs hub/ vs spoke/)
5. Update documentation to reference legacy source
6. Add commit message explaining what was ported and why

## References

- **Unified role implementation**: `playbooks/telco-kpis/roles/lockdowns/`
- **Legacy implementation branch**: `ipa-telco-kpis-prow-migration-20260619-before-deploy-ocp-operators-untouched`
- **Upstream playbook**: `playbooks/deploy-ocp-operators.yml`
- **Wrapper playbook**: `playbooks/telco-kpis/deploy-ocp-operators.yml`
- **Design docs**: `/docs/designs/operator-lockdown-*.md`
