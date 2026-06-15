# Spoke Hub Connectivity - Check Status Tests

This molecule scenario tests the check-status template generation for the spoke_hub_connectivity role.

## Test Scope

Validates that the check-status templates (`check-bmc-iptables-rules.sh.j2`, `check-cluster-iptables-rules.sh.j2`, `check-registry-iptables-rules.sh.j2`) render correctly with proper variable substitution.

## Test Phases

### 1. Prepare
- Creates `/tmp/molecule-tests/check-status/` directory
- Sets up mock spoke-hub connectivity variables (IPs, ports, names)

### 2. Converge
- Renders all 3 check-status templates
- Reads generated scripts back as facts

### 3. Verify
- **10 assertions** validate:
  - Correct shebang (`#!/bin/bash`)
  - Proper variable substitution (SOURCE_RANGE, HV_IP, HUB_IP, BASTION_IP, TOTAL)
  - All required ports present in scripts
  - Correct iptables commands (PREROUTING chain)
  - Output format (`${FOUND}/${TOTAL}`)

## Running Tests

```bash
# Run from role directory
make test-check

# Or run individual phases (requires ansible locally)
make prepare
make converge
make verify

# Clean up
make clean
```

## Test Data

- **Spoke**: spoke-01 (BMC: 10.6.214.10, Cluster: 10.6.214.20)
- **Hub**: dev-kpi-01 (Cluster: 10.6.204.64, Bastion: 10.6.204.37)
- **Hypervisor**: localhost (Corporate IP: 10.19.138.54)
- **BMC Ports**: 6180, 6181, 6183, 6385
- **Cluster Ports**: 80, 443, 6443, 22624
- **Registry Ports**: 5000

## Expected Results

All assertions should pass, confirming templates render correctly for the check-status action.
