#!/usr/bin/env bash

set -euo pipefail

# Source the tuples configuration
source tests.bash

echo "Running Ansible Playbook Sanity Checks..."

function run_sanity_test() {
    local inventory="${1}"
    local playbook="${2}"
    local cmd=()

    if [[ ! -f "${inventory}" ]]; then
        echo "ERROR: Inventory file '${inventory}' not found"
        exit 1
    fi

    if [[ ! -f "${playbook}" ]]; then
        echo "ERROR: Playbook file '${playbook}' not found"
        exit 1
    fi

    cmd+=("ansible-playbook" "-i" "${inventory}" "${playbook}" "--check")
    echo "Running: ${cmd[*]}"

    if ! "${cmd[@]}"; then
        echo "ERROR: Sanity check failed for playbook '${playbook}' with inventory '${inventory}'"
        exit 1
    fi
    echo "✓ Sanity check passed for: ${playbook}"
    return 0
}

for tuple in "${TUPLES[@]}"; do
    IFS=':' read -r inventory playbook <<<"${tuple}"
    run_sanity_test "${inventory}" "${playbook}"
done

echo "All Ansible playbook sanity checks completed successfully!"
