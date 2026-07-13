# Spoke Hub Connectivity - Remove Tests

This molecule scenario tests the remove-iptables template generation for the spoke_hub_connectivity role.

## Test Scope

Validates that the removal templates (`remove-bmc-iptables-rules.sh.j2`, `remove-cluster-iptables-rules.sh.j2`, `remove-registry-iptables-rules.sh.j2`) render correctly with proper variable substitution and include proper error handling.

## Test Phases

### 1. Prepare
- Creates `/tmp/molecule-tests/remove/` directory
- Sets up mock spoke-hub connectivity variables (IPs, ports, names)
- Sets `item` variable to simulate loop context

### 2. Converge
- Renders all 3 removal templates with loop variable
- Reads generated scripts back as facts

### 3. Verify
- **10 assertions** validate:
  - Correct shebang (`#!/bin/bash`) and error handling (`set -e`)
  - Proper variable substitution (SOURCE_RANGE, HV_IP, HUB_IP, BASTION_IP, PORT)
  - All iptables removal commands present (PREROUTING, POSTROUTING, FORWARD)
  - DNAT and MASQUERADE directives
  - Error handling (`2>/dev/null` and `|| true`)

## Running Tests

```bash
# Run from role directory
make test-remove

# Clean up
make clean
```

## Test Data

- **Spoke**: spoke-02 (BMC: 10.6.215.10/32, Cluster: 10.6.215.20/32)
- **Hub**: dev-kpi-02 (Cluster: 10.6.205.64, Bastion: 10.6.205.37)
- **Hypervisor**: localhost (Corporate IP: 10.19.138.55)
- **Test Port**: 6180 (simulates loop item)

## Expected Results

All assertions should pass, confirming removal templates render correctly with proper error handling for the remove-iptables action.
