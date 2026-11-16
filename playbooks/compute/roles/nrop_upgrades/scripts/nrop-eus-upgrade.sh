#!/bin/bash
# EUS worker pause and bulk unpause.
# Canary migration lives in nrop-canary-skip-upgrade.sh.
set -euo pipefail

PHASE="${1:?Usage: nrop-eus-upgrade.sh <setup|unpause>}"
NROP_MCP_TARGET="${NROP_MCP_TARGET:-worker}"
OCP_TARGET_VERSION="${OCP_TARGET_VERSION:-}"
OCP_FROM_MINOR="${OCP_FROM_MINOR:-0}"
ARTIFACTS_DIR="${ARTIFACTS_DIR:-${WORKSPACE:-/tmp}/artifacts}"
SELINUX_KEY="config.node.openshift-kni.io/selinux-policy"

mkdir -p "${ARTIFACTS_DIR}"

pause_nrop_reconciliation() {
    oc annotate numaresourcesoperator numaresourcesoperator \
        config.numa-operator.openshift.io/pause-reconciliation=enabled --overwrite
    local pause_val
    pause_val=$(oc get numaresourcesoperator numaresourcesoperator -o json \
        | jq -r '.metadata.annotations["config.numa-operator.openshift.io/pause-reconciliation"] // "missing"')
    if [[ "${pause_val}" != "enabled" ]]; then
        echo "[FATAL] pause-reconciliation annotation was not applied. Got: ${pause_val}"
        exit 1
    fi
    echo "[VERIFY] pause-reconciliation annotation set to enabled"
}

resume_nrop_reconciliation() {
    oc annotate numaresourcesoperator numaresourcesoperator \
        config.numa-operator.openshift.io/pause-reconciliation- --overwrite
    local pause_val
    pause_val=$(oc get numaresourcesoperator numaresourcesoperator -o json \
        | jq -r '.metadata.annotations["config.numa-operator.openshift.io/pause-reconciliation"] // "removed"')
    if [[ "${pause_val}" != "removed" ]]; then
        echo "[FATAL] pause-reconciliation annotation was not removed. Got: ${pause_val}"
        exit 1
    fi
    echo "[VERIFY] pause-reconciliation annotation removed"
}

set_eus_channel() {
    if [[ -z "${OCP_TARGET_VERSION}" ]]; then
        echo "[FATAL] OCP_TARGET_VERSION is required to set the EUS channel"
        exit 1
    fi
    echo "[INFO] Setting update channel to eus-${OCP_TARGET_VERSION}"
    oc adm upgrade channel "eus-${OCP_TARGET_VERSION}"
    local actual_channel
    actual_channel=$(oc get clusterversion version -o jsonpath='{.spec.channel}')
    if [[ "${actual_channel}" != "eus-${OCP_TARGET_VERSION}" ]]; then
        echo "[FATAL] EUS channel was not set. Expected eus-${OCP_TARGET_VERSION}, got ${actual_channel}"
        exit 1
    fi
    echo "[VERIFY] Update channel set to ${actual_channel}"
}

set_worker_paused() {
    local want="$1"
    oc patch "mcp/${NROP_MCP_TARGET}" --type merge --patch "{\"spec\":{\"paused\":${want}}}"
    local paused
    paused=$(oc get mcp "${NROP_MCP_TARGET}" -o jsonpath='{.spec.paused}' 2>/dev/null || echo "false")
    if [[ "${want}" == "true" && "${paused}" != "true" ]]; then
        echo "[FATAL] MCP ${NROP_MCP_TARGET} is not paused. Got: ${paused}"
        exit 1
    fi
    if [[ "${want}" == "false" && "${paused}" == "true" ]]; then
        echo "[FATAL] MCP ${NROP_MCP_TARGET} is still paused"
        exit 1
    fi
    echo "[VERIFY] MCP ${NROP_MCP_TARGET} paused=${paused}"
}

worker_selinux_annotation_value() {
    oc get numaresourcesoperator numaresourcesoperator -o json \
        | jq -r --arg mcp "${NROP_MCP_TARGET}" --arg key "${SELINUX_KEY}" '
            [.spec.nodeGroups[]?
              | select(
                  (.machineConfigPoolSelector.matchLabels[
                    "pools.operator.machineconfiguration.openshift.io/" + $mcp
                  ] != null)
                  or (.poolName == $mcp)
                )
              | .annotations[$key] // "missing"
            ] | first // "missing"'
}

patch_selinux() {
    local action="$1"
    local worker_groups
    worker_groups=$(oc get numaresourcesoperator numaresourcesoperator -o json \
        | jq -r --arg mcp "${NROP_MCP_TARGET}" \
          '[.spec.nodeGroups[]?
            | select(
                (.machineConfigPoolSelector.matchLabels[
                  "pools.operator.machineconfiguration.openshift.io/" + $mcp
                ] != null)
                or (.poolName == $mcp)
              )] | length')
    if [[ "${worker_groups}" == "0" ]]; then
        echo "[FATAL] NROP CR has no nodeGroup for MCP ${NROP_MCP_TARGET}"
        oc get numaresourcesoperator numaresourcesoperator -o yaml
        exit 1
    fi

    oc get numaresourcesoperator numaresourcesoperator -o json \
        | jq --arg action "${action}" --arg key "${SELINUX_KEY}" --arg mcp "${NROP_MCP_TARGET}" '
            del(.status, .metadata.managedFields, .metadata.resourceVersion, .metadata.uid, .metadata.generation, .metadata.creationTimestamp)
            | if (.spec.nodeGroups | length) < 1 then error("NROP CR has no nodeGroups") else . end
            | .spec.nodeGroups |= map(
                if ((.machineConfigPoolSelector.matchLabels[
                       "pools.operator.machineconfiguration.openshift.io/" + $mcp
                     ] != null)
                    or (.poolName == $mcp)) then
                  .annotations |= (. // {})
                  | if $action == "add" then
                      .annotations[$key] = "custom"
                    else
                      .annotations |= del(.[$key])
                    end
                else
                  .
                end
              )
          ' > "${ARTIFACTS_DIR}/nrop-cr-eus-selinux.json"
    oc apply -f "${ARTIFACTS_DIR}/nrop-cr-eus-selinux.json"

    local ann_val
    ann_val="$(worker_selinux_annotation_value)"
    if [[ "${action}" == "add" && "${ann_val}" != "custom" ]]; then
        echo "[FATAL] SELinux annotation was not set on ${NROP_MCP_TARGET} nodeGroup. Got: ${ann_val}"
        oc get numaresourcesoperator numaresourcesoperator -o yaml
        exit 1
    fi
    if [[ "${action}" == "remove" && "${ann_val}" != "missing" ]]; then
        echo "[FATAL] SELinux annotation was not removed from ${NROP_MCP_TARGET} nodeGroup. Got: ${ann_val}"
        oc get numaresourcesoperator numaresourcesoperator -o yaml
        exit 1
    fi
    echo "[VERIFY] SELinux annotation ${action} on ${NROP_MCP_TARGET} nodeGroup: ${ann_val}"
}

wait_for_worker_mcp() {
    local expected
    expected=$(oc get nodes -l "node-role.kubernetes.io/${NROP_MCP_TARGET}=" --no-headers 2>/dev/null | wc -l | tr -d ' ')
    echo "[INFO] Waiting for MCP ${NROP_MCP_TARGET} to update ${expected} worker(s)"
    local i updated updating degraded machine_count ready_count
    for ((i = 1; i <= 120; i++)); do
        updated=$(oc get mcp "${NROP_MCP_TARGET}" -o jsonpath='{.status.conditions[?(@.type=="Updated")].status}' 2>/dev/null || echo "Unknown")
        updating=$(oc get mcp "${NROP_MCP_TARGET}" -o jsonpath='{.status.conditions[?(@.type=="Updating")].status}' 2>/dev/null || echo "Unknown")
        degraded=$(oc get mcp "${NROP_MCP_TARGET}" -o jsonpath='{.status.conditions[?(@.type=="Degraded")].status}' 2>/dev/null || echo "Unknown")
        machine_count=$(oc get mcp "${NROP_MCP_TARGET}" -o jsonpath='{.status.machineCount}' 2>/dev/null || echo "0")
        ready_count=$(oc get mcp "${NROP_MCP_TARGET}" -o jsonpath='{.status.readyMachineCount}' 2>/dev/null || echo "0")
        echo "[INFO] MCP ${NROP_MCP_TARGET}: Updated=${updated} Updating=${updating} Degraded=${degraded} ready=${ready_count}/${machine_count} (attempt ${i}/120)"
        if [[ "${updated}" == "True" && "${updating}" == "False" && "${degraded}" == "False" && "${machine_count}" -ge "${expected}" && "${machine_count}" -gt 0 && "${ready_count}" == "${machine_count}" ]]; then
            echo "[VERIFY] MCP ${NROP_MCP_TARGET} is updated"
            return 0
        fi
        sleep 30
    done
    echo "[FATAL] MCP ${NROP_MCP_TARGET} did not finish the worker update"
    oc get mcp "${NROP_MCP_TARGET}" -o yaml
    exit 1
}

phase_setup() {
    echo "[INFO] === EUS SETUP ==="
    pause_nrop_reconciliation
    set_eus_channel
    set_worker_paused true
    oc get mcp -o wide
    echo "[INFO] === EUS SETUP COMPLETE ==="
}

phase_unpause() {
    echo "[INFO] === EUS UNPAUSE WORKERS ==="
    if [[ "${OCP_FROM_MINOR}" -lt 18 ]]; then
        echo "[INFO] Source minor ${OCP_FROM_MINOR} is below 18. Setting the custom SELinux policy before workers move."
        patch_selinux add
    else
        echo "[INFO] Source minor ${OCP_FROM_MINOR} uses the built-in SELinux policy. Skipping the annotation."
    fi
    resume_nrop_reconciliation
    set_worker_paused false
    wait_for_worker_mcp
    if [[ "${OCP_FROM_MINOR}" -lt 18 ]]; then
        patch_selinux remove
    fi
    oc get mcp -o wide
    oc get nodes -o wide
    echo "[INFO] === EUS UNPAUSE COMPLETE ==="
}

case "${PHASE}" in
    setup) phase_setup ;;
    unpause) phase_unpause ;;
    *)
        echo "Usage: nrop-eus-upgrade.sh <setup|unpause>" >&2
        exit 2
        ;;
esac
