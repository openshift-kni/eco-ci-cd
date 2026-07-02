# Spoke Hub Connectivity Role - Molecule Tests

Molecule test suites for the `spoke_hub_connectivity` role, focusing on template generation and validation.

## Test Scenarios

### 1. check-status
Tests the three check-status template scripts:
- `check-bmc-iptables-rules.sh.j2` - Validates BMC → Hub cluster rules
- `check-cluster-iptables-rules.sh.j2` - Validates Cluster → Hub cluster rules
- `check-registry-iptables-rules.sh.j2` - Validates Cluster → Hub bastion (registry) rules

**Assertions**: 10 (validates shebang, variables, ports, iptables commands, output format)

### 2. remove
Tests the three removal template scripts:
- `remove-bmc-iptables-rules.sh.j2` - Removes BMC traffic rules
- `remove-cluster-iptables-rules.sh.j2` - Removes cluster traffic rules
- `remove-registry-iptables-rules.sh.j2` - Removes registry traffic rules

**Assertions**: 10 (validates shebang, set -e, variables, iptables removal commands, error handling)

## Running Tests

```bash
# Run all tests
make test

# Run specific scenario
make test-check
make test-remove

# Run individual phases (for debugging)
make prepare
make converge
make verify

# Clean up test artifacts
make clean

# Show help
make help
```

## Test Architecture

All tests follow the same three-phase pattern:

1. **Prepare**: Sets up mock variables and test environment
2. **Converge**: Generates templates and reads them back as facts
3. **Verify**: Runs assertions to validate template correctness

Tests run in containerized environment using `quay.io/ccardenosa/eco-ci-cd:latest` for consistency.

## What's NOT Tested

- **setup-iptables**: Uses `ansible.posix.firewalld` module directly (no templates)
- **update-provisioning-cr**: Single-use template, minimal complexity
- **list-interconnections**: Simple grep command, no template complexity
- **validate-bmc**: Logic validation, not template-based
- **update-dns**: Uses Ansible modules, not templates

The test suite focuses on the refactored template-based scripts (check and remove operations) which are the most complex and error-prone parts of the role.

## Test Coverage

- ✅ Template variable substitution
- ✅ Script syntax (shebang, set -e)
- ✅ iptables command correctness
- ✅ Port configuration
- ✅ Error handling (|| true, 2>/dev/null)
- ✅ Output format validation

## Requirements

- Podman (for running containerized tests)
- Ansible (for local debugging phases only)

Tests are designed to run without requiring:
- Real hypervisor access
- Actual iptables execution
- SSH connectivity
- Vault credentials
