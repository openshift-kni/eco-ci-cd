#!/bin/bash
# Canary worker migration and cleanup.
# NROP_CANARY_TUNING_V1
# NROP_CANARY_CLEANUP_V2
# NROP_CANARY_SMOKE_V3
set -ex

PHASE="${1:?Usage: nrop-canary-skip-upgrade.sh <setup|migrate|cleanup|normalize>}"
NROP_MCP_TARGET="${NROP_MCP_TARGET:-worker}"
UPGRADE_MCP_NAME="${UPGRADE_MCP_NAME:-${NROP_MCP_TARGET}-upgrade}"
MANAGED_CANARY_PROFILE="${MANAGED_CANARY_PROFILE:-}"
MANAGED_CANARY_KUBELET="${MANAGED_CANARY_KUBELET:-}"
MANAGED_WORKER_KUBELET="${MANAGED_WORKER_KUBELET:-}"
TOPOLOGY_MANAGER_SCOPE="${TOPOLOGY_MANAGER_SCOPE:-pod}"
NROP_TEMP_NODEGROUP_CONFIG_JSON="${NROP_TEMP_NODEGROUP_CONFIG_JSON:-}"
NROP_ORIGINAL_NODEGROUP_CONFIG_JSON="${NROP_ORIGINAL_NODEGROUP_CONFIG_JSON:-}"
NROP_FINGERPRINT_CR_UID="${NROP_FINGERPRINT_CR_UID:-}"
ARTIFACTS_DIR="${ARTIFACTS_DIR:-${WORKSPACE:-/tmp}/artifacts}"
mkdir -p "${ARTIFACTS_DIR}"
CANARY_NODE_COUNT="${CANARY_NODE_COUNT:-0}"
# Source OCP minor version — used to decide whether the SELinux annotation is needed.
# The SELinux policy changed at 4.18: upgrades from pre-4.18 require the custom annotation;
# upgrades from 4.18+ (e.g., 4.18->4.20, 4.20->4.22) share the same built-in policy and skip it.
OCP_FROM_MINOR="${OCP_FROM_MINOR:-0}"

collect_debug_logs() {
    echo "[INFO] === Collecting debug logs ==="
    oc get clusterversion -o yaml > "${ARTIFACTS_DIR}/canary-debug-clusterversion.yaml" 2>&1 || true
    oc get clusterversion version -o json | jq '.status.conditions' > "${ARTIFACTS_DIR}/canary-debug-cv-conditions.json" 2>&1 || true

    oc get pods -n openshift-numaresources -o wide > "${ARTIFACTS_DIR}/canary-debug-nrop-pods.txt" 2>&1 || true
    oc get mcp -o wide > "${ARTIFACTS_DIR}/canary-debug-mcp-status.txt" 2>&1 || true
    oc get nodes -o wide > "${ARTIFACTS_DIR}/canary-debug-nodes.txt" 2>&1 || true
    oc get numaresourcesoperator numaresourcesoperator -o yaml > "${ARTIFACTS_DIR}/canary-debug-nrop-cr.yaml" 2>&1 || true

    local rte_pods
    rte_pods=$(oc get pods -n openshift-numaresources -l name=resource-topology -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || true)
    if [[ -n "${rte_pods}" ]]; then
        for pod in ${rte_pods}; do
            echo "[INFO] Collecting logs for RTE pod ${pod}"
            oc logs -n openshift-numaresources "${pod}" --all-containers > "${ARTIFACTS_DIR}/canary-debug-rte-${pod}.log" 2>&1 || true
        done
    else
        echo "[WARNING] No RTE pods found with label name=resource-topology, trying broader search"
        rte_pods=$(oc get pods -n openshift-numaresources --no-headers -o custom-columns=NAME:.metadata.name 2>/dev/null | grep -i rte || true)
        for pod in ${rte_pods}; do
            echo "[INFO] Collecting logs for pod ${pod}"
            oc logs -n openshift-numaresources "${pod}" --all-containers > "${ARTIFACTS_DIR}/canary-debug-rte-${pod}.log" 2>&1 || true
        done
    fi

    echo "[INFO] === Debug logs collected in ${ARTIFACTS_DIR}/canary-debug-* ==="
}

trap 'collect_debug_logs' ERR

move_worker_to_upgrade() {
    local node="$1"
    if [[ "${NROP_MCP_TARGET}" == "worker" ]]; then
        oc label node "${node}" "node-role.kubernetes.io/${UPGRADE_MCP_NAME}=" --overwrite
    else
        # Switch custom roles atomically, preserving the built-in worker role.
        oc label node "${node}" "node-role.kubernetes.io/${NROP_MCP_TARGET}-" \
            "node-role.kubernetes.io/${UPGRADE_MCP_NAME}=" --overwrite
    fi
}

return_worker_to_regular() {
    local node="$1"
    if [[ "${NROP_MCP_TARGET}" == "worker" ]]; then
        oc label node "${node}" "node-role.kubernetes.io/${UPGRADE_MCP_NAME}-" --overwrite
    else
        oc label node "${node}" "node-role.kubernetes.io/${UPGRADE_MCP_NAME}-" \
            "node-role.kubernetes.io/${NROP_MCP_TARGET}=" --overwrite
    fi
}

wait_for_mcp_stable() {
    local mcp_name="$1"
    local max_retries="${2:-120}"
    local delay="${3:-30}"
    local min_machines="${4:-0}"

    echo "[INFO] Waiting for MCP ${mcp_name} to stabilize (up to $((max_retries * delay / 60)) min, min_machines=${min_machines})..."
    for ((i=1; i<=max_retries; i++)); do
        local updated degraded updating machine_count ready_count updated_count spec_config status_config
        updated=$(oc get mcp "${mcp_name}" -o jsonpath='{.status.conditions[?(@.type=="Updated")].status}' 2>/dev/null || echo "Unknown")
        degraded=$(oc get mcp "${mcp_name}" -o jsonpath='{.status.conditions[?(@.type=="Degraded")].status}' 2>/dev/null || echo "Unknown")
        updating=$(oc get mcp "${mcp_name}" -o jsonpath='{.status.conditions[?(@.type=="Updating")].status}' 2>/dev/null || echo "Unknown")
        machine_count=$(oc get mcp "${mcp_name}" -o jsonpath='{.status.machineCount}' 2>/dev/null || echo "0")
        ready_count=$(oc get mcp "${mcp_name}" -o jsonpath='{.status.readyMachineCount}' 2>/dev/null || echo "0")
        updated_count=$(oc get mcp "${mcp_name}" -o jsonpath='{.status.updatedMachineCount}' 2>/dev/null || echo "0")
        spec_config=$(oc get mcp "${mcp_name}" -o jsonpath='{.spec.configuration.name}' 2>/dev/null || echo "")
        status_config=$(oc get mcp "${mcp_name}" -o jsonpath='{.status.configuration.name}' 2>/dev/null || echo "")

        echo "[INFO] MCP ${mcp_name}: Updated=${updated}, Updating=${updating}, Degraded=${degraded}, Machines=${machine_count}/${ready_count} ready (attempt ${i}/${max_retries})"

        if [[ "${updated}" == "True" && "${updating}" == "False" && "${degraded}" == "False" && "${machine_count}" -ge "${min_machines}" && "${machine_count}" -gt 0 && "${ready_count}" == "${machine_count}" && "${updated_count}" == "${machine_count}" && -n "${spec_config}" && "${spec_config}" == "${status_config}" ]]; then
            echo "[INFO] MCP ${mcp_name} is stable (${machine_count} machines, all ready)"
            return 0
        fi

        if [[ "${degraded}" == "True" && $((i % 10)) -eq 0 ]]; then
            local degraded_msg
            degraded_msg=$(oc get mcp "${mcp_name}" -o jsonpath='{.status.conditions[?(@.type=="Degraded")].message}' 2>/dev/null || echo "unknown")
            echo "[DIAG] MCP ${mcp_name} Degraded message: ${degraded_msg}"
            echo "[DIAG] Node status:"
            oc get nodes -o custom-columns=NAME:.metadata.name,STATUS:.status.conditions[-1:].type,READY:.status.conditions[-1:].status,VERSION:.status.nodeInfo.kubeletVersion 2>/dev/null || true
            echo "[DIAG] MCP details:"
            oc get mcp "${mcp_name}" -o jsonpath='{.status.conditions[*].type}{"\n"}{.status.conditions[*].status}{"\n"}{.status.conditions[*].message}{"\n"}' 2>/dev/null || true
        fi

        sleep "${delay}"
    done
    echo "[ERROR] MCP ${mcp_name} did not stabilize within timeout"
    echo "[DIAG] Final MCP state:"
    oc get mcp "${mcp_name}" -o yaml 2>/dev/null || true
    echo "[DIAG] Final node state:"
    oc get nodes -o wide 2>/dev/null || true
    return 1
}

wait_for_node_ready() {
    local node_name="$1"
    local max_retries="${2:-120}"
    local delay="${3:-30}"

    echo "[INFO] Waiting for node ${node_name} to become Ready (up to $((max_retries * delay / 60)) min)..."
    for ((i=1; i<=max_retries; i++)); do
        local status
        status=$(oc get node "${node_name}" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "Unknown")
        echo "[INFO] Node ${node_name} Ready=${status} (attempt ${i}/${max_retries})"
        if [[ "${status}" == "True" ]]; then
            echo "[INFO] Node ${node_name} is Ready"
            return 0
        fi
        sleep "${delay}"
    done
    echo "[ERROR] Node ${node_name} did not become Ready within timeout"
    return 1
}

assert_rte_pod_running_on_node() {
    local node_name="$1"
    local max_retries="${2:-20}"
    local delay="${3:-15}"

    echo "[INFO] Verifying RTE pod is running on node ${node_name}..."
    for ((i=1; i<=max_retries; i++)); do
        local pod_info
        pod_info=$(oc get pods -n openshift-numaresources -l name=resource-topology \
            --field-selector "spec.nodeName=${node_name}" \
            --no-headers -o custom-columns=NAME:.metadata.name,STATUS:.status.phase 2>/dev/null || true)

        if [[ -n "${pod_info}" ]]; then
            local found_running=false
            while IFS= read -r line; do
                local pod_name pod_status
                pod_name=$(echo "${line}" | awk '{print $1}')
                pod_status=$(echo "${line}" | awk '{print $2}')
                echo "[INFO] RTE pod on ${node_name}: ${pod_name} = ${pod_status}"
                if [[ "${pod_status}" == "Running" ]]; then
                    found_running=true
                fi
            done <<< "${pod_info}"

            if [[ "${found_running}" == "true" ]]; then
                echo "[VERIFY] At least one RTE pod is Running on node ${node_name}"
                return 0
            fi

            echo "[WARNING] No RTE pod in Running state on node ${node_name} (attempt ${i}/${max_retries})"

            if [[ "${i}" == "${max_retries}" ]]; then
                echo "[FATAL] No RTE pod on node ${node_name} reached Running state!"
                echo "[FATAL] === Collecting failed RTE pod diagnostics ==="
                echo "--- All NROP pods ---"
                oc get pods -n openshift-numaresources -o wide 2>&1 | tee "${ARTIFACTS_DIR}/canary-rte-all-pods-after-failure.txt" || true
                echo "--- NROP CR ---"
                oc get numaresourcesoperator numaresourcesoperator -o yaml 2>&1 | tee "${ARTIFACTS_DIR}/canary-rte-nrop-cr-after-failure.yaml" || true
                echo "--- DaemonSets ---"
                oc get daemonsets -n openshift-numaresources -o wide 2>&1 | tee "${ARTIFACTS_DIR}/canary-rte-daemonsets.txt" || true
                echo "--- Node labels ---"
                oc get node "${node_name}" -o json | jq '.metadata.labels' 2>&1 | tee "${ARTIFACTS_DIR}/canary-rte-node-labels-${node_name}.json" || true
                exit 1
            fi
        else
            echo "[INFO] No RTE pod found on node ${node_name} yet (attempt ${i}/${max_retries})"

            if [[ "${i}" == "${max_retries}" ]]; then
                echo "[FATAL] No RTE pod was scheduled on node ${node_name} after migration!"
                echo "[FATAL] === Collecting diagnostics ==="
                echo "--- All NROP pods ---"
                oc get pods -n openshift-numaresources -o wide 2>&1 | tee "${ARTIFACTS_DIR}/canary-rte-no-pod-on-${node_name}.txt" || true
                echo "--- NROP CR ---"
                oc get numaresourcesoperator numaresourcesoperator -o yaml 2>&1 | tee "${ARTIFACTS_DIR}/canary-rte-nrop-cr-after-failure.yaml" || true
                echo "--- DaemonSets ---"
                oc get daemonsets -n openshift-numaresources -o wide 2>&1 | tee "${ARTIFACTS_DIR}/canary-rte-daemonsets.txt" || true
                echo "--- Node labels ---"
                oc get node "${node_name}" -o json | jq '.metadata.labels' 2>&1 | tee "${ARTIFACTS_DIR}/canary-rte-node-labels-${node_name}.json" || true
                exit 1
            fi
        fi
        sleep "${delay}"
    done
}

assert_rte_pod_ready_for_mcp() {
    local mcp_name="$1"
    local node_name="$2"
    local max_retries="${3:-20}"
    local delay="${4:-15}"

    echo "[INFO] Verifying ${mcp_name} RTE pod has full readiness on node ${node_name}..."
    for ((i=1; i<=max_retries; i++)); do
        local pod_ready
        pod_ready=$(oc get pods -n openshift-numaresources \
            -l "name=resource-topology" \
            --field-selector "spec.nodeName=${node_name}" \
            --no-headers -o custom-columns=NAME:.metadata.name,READY:.status.containerStatuses[*].ready,GATES:.status.conditions[*].status \
            2>/dev/null | grep "${mcp_name}" | head -1 || true)

        if [[ -n "${pod_ready}" ]]; then
            local pod_name
            pod_name=$(echo "${pod_ready}" | awk '{print $1}')

            local ready_count not_ready_count
            ready_count=$(oc get pod -n openshift-numaresources "${pod_name}" -o json 2>/dev/null \
                | jq '[.status.conditions[]? | select(.status=="True")] | length' || echo "0")
            local total_conditions
            total_conditions=$(oc get pod -n openshift-numaresources "${pod_name}" -o json 2>/dev/null \
                | jq '[.status.conditions[]?] | length' || echo "0")

            echo "[INFO] ${mcp_name} RTE pod ${pod_name}: ${ready_count}/${total_conditions} conditions True (attempt ${i}/${max_retries})"

            local gates_met
            gates_met=$(oc get pod -n openshift-numaresources "${pod_name}" -o json 2>/dev/null \
                | jq '[.status.conditions[]? | select(.type | test("Ready$|ContainersReady$|PodresourcesFetched$|NodeTopologyUpdated$")) | select(.status=="True")] | length' || echo "0")

            if [[ "${gates_met}" -ge 4 ]]; then
                echo "[VERIFY] ${mcp_name} RTE pod ${pod_name} is fully ready (${gates_met} key conditions met)"
                return 0
            fi
        else
            echo "[INFO] No ${mcp_name} RTE pod found on ${node_name} yet (attempt ${i}/${max_retries})"
        fi

        if [[ "${i}" == "${max_retries}" ]]; then
            echo "[FATAL] ${mcp_name} RTE pod on ${node_name} did not reach full readiness within timeout"
            echo "--- Pod details ---"
            oc get pods -n openshift-numaresources -l name=resource-topology \
                --field-selector "spec.nodeName=${node_name}" -o wide 2>&1 || true
            return 1
        fi
        sleep "${delay}"
    done
}

collect_nrop_operator_logs() {
    local label="$1"
    echo "[INFO] Collecting NROP operator logs (${label})..."
    local operator_pod
    operator_pod=$(oc get pods -n openshift-numaresources -l control-plane=controller-manager \
        --no-headers -o custom-columns=NAME:.metadata.name 2>/dev/null | head -1 || true)
    if [[ -z "${operator_pod}" ]]; then
        operator_pod=$(oc get pods -n openshift-numaresources --no-headers \
            -o custom-columns=NAME:.metadata.name 2>/dev/null | grep "controller-manager" | head -1 || true)
    fi
    if [[ -n "${operator_pod}" ]]; then
        oc logs -n openshift-numaresources "${operator_pod}" --all-containers \
            > "${ARTIFACTS_DIR}/canary-nrop-operator-logs-${label}.log" 2>&1 || true
        echo "[INFO] NROP operator logs saved to canary-nrop-operator-logs-${label}.log (pod: ${operator_pod})"
    else
        echo "[WARNING] Could not find NROP operator pod to collect logs"
    fi
}

assert_rte_daemonset_status() {
    local node_name="$1"
    echo "[INFO] Checking RTE DaemonSet status after migrating node ${node_name}..."

    echo "--- DaemonSets ---"
    oc get daemonsets -n openshift-numaresources -o wide 2>&1 | tee "${ARTIFACTS_DIR}/canary-daemonsets-after-${node_name}.txt"

    local ds_list
    ds_list=$(oc get daemonsets -n openshift-numaresources -l name=resource-topology \
        --no-headers -o custom-columns=NAME:.metadata.name 2>/dev/null || true)

    if [[ -z "${ds_list}" ]]; then
        ds_list=$(oc get daemonsets -n openshift-numaresources \
            --no-headers -o custom-columns=NAME:.metadata.name 2>/dev/null | grep "numaresourcesoperator" || true)
    fi

    local ds_count
    ds_count=$(echo "${ds_list}" | grep -c . || true)
    echo "[INFO] Found ${ds_count} RTE DaemonSet(s): ${ds_list}"

    for ds in ${ds_list}; do
        local desired ready available unavailable
        desired=$(oc get daemonset -n openshift-numaresources "${ds}" -o jsonpath='{.status.desiredNumberScheduled}' 2>/dev/null || echo "0")
        ready=$(oc get daemonset -n openshift-numaresources "${ds}" -o jsonpath='{.status.numberReady}' 2>/dev/null || echo "0")
        available=$(oc get daemonset -n openshift-numaresources "${ds}" -o jsonpath='{.status.numberAvailable}' 2>/dev/null || echo "0")
        unavailable=$(oc get daemonset -n openshift-numaresources "${ds}" -o jsonpath='{.status.numberUnavailable}' 2>/dev/null || echo "0")

        echo "[INFO] DaemonSet ${ds}: desired=${desired}, ready=${ready}, available=${available}, unavailable=${unavailable}"

        if [[ "${unavailable}" -gt 0 ]]; then
            echo "[WARNING] DaemonSet ${ds} has ${unavailable} unavailable pod(s)"
            echo "--- DaemonSet YAML ---"
            oc get daemonset -n openshift-numaresources "${ds}" -o yaml > "${ARTIFACTS_DIR}/canary-ds-${ds}-after-${node_name}.yaml" 2>&1 || true
        fi

        if [[ "${desired}" -gt 0 && "${ready}" == "${desired}" ]]; then
            echo "[VERIFY] DaemonSet ${ds}: all ${desired} pods are ready"
        elif [[ "${desired}" == "0" ]]; then
            echo "[INFO] DaemonSet ${ds}: 0 desired pods (no matching nodes)"
        else
            echo "[WARNING] DaemonSet ${ds}: ${ready}/${desired} pods ready"
        fi
    done

    echo "--- RTE Pods ---"
    oc get pods -n openshift-numaresources -l name=resource-topology -o wide 2>&1 | tee "${ARTIFACTS_DIR}/canary-rte-pods-after-${node_name}.txt"
}

assert_rte_daemonset_for_mcp() {
    local mcp_name="$1"
    local max_retries="${2:-20}"
    local delay="${3:-15}"

    echo "[INFO] Verifying RTE DaemonSet exists for MCP ${mcp_name}..."
    for ((i=1; i<=max_retries; i++)); do
        local ds_name
        ds_name=$(oc get daemonsets -n openshift-numaresources --no-headers \
            -o custom-columns=NAME:.metadata.name 2>/dev/null | grep "${mcp_name}" || true)

        if [[ -n "${ds_name}" ]]; then
            local desired ready
            desired=$(oc get daemonset -n openshift-numaresources "${ds_name}" -o jsonpath='{.status.desiredNumberScheduled}' 2>/dev/null || echo "0")
            ready=$(oc get daemonset -n openshift-numaresources "${ds_name}" -o jsonpath='{.status.numberReady}' 2>/dev/null || echo "0")
            echo "[VERIFY] RTE DaemonSet '${ds_name}' found for MCP ${mcp_name}: desired=${desired}, ready=${ready}"
            oc get daemonset -n openshift-numaresources "${ds_name}" -o wide 2>&1 | tee "${ARTIFACTS_DIR}/canary-ds-${mcp_name}-verified.txt"
            return 0
        fi

        echo "[INFO] No RTE DaemonSet found for MCP ${mcp_name} yet (attempt ${i}/${max_retries})"
        sleep "${delay}"
    done

    echo "[FATAL] No RTE DaemonSet was created for MCP ${mcp_name}!"
    echo "--- All DaemonSets ---"
    oc get daemonsets -n openshift-numaresources -o wide 2>&1 | tee "${ARTIFACTS_DIR}/canary-ds-missing-${mcp_name}.txt"
    echo "--- NROP CR ---"
    oc get numaresourcesoperator numaresourcesoperator -o yaml 2>&1 | tee "${ARTIFACTS_DIR}/canary-nrop-cr-missing-ds-${mcp_name}.yaml"
    exit 1
}

assert_nrop_upgrade_nodegroup() {
    local count
    count=$(oc get numaresourcesoperator numaresourcesoperator -o json \
        | jq -r --arg mcp "${UPGRADE_MCP_NAME}" \
          '[.spec.nodeGroups // [] | .[] | select(.machineConfigPoolSelector.matchLabels["pools.operator.machineconfiguration.openshift.io/" + $mcp] != null)] | length')
    if [[ "${count}" == "0" ]]; then
        echo "[FATAL] NROP CR is missing ${UPGRADE_MCP_NAME} nodeGroup after patch!"
        oc get numaresourcesoperator numaresourcesoperator -o yaml
        exit 1
    fi
    echo "[VERIFY] ${UPGRADE_MCP_NAME} nodeGroup confirmed in NROP CR (found ${count})"
}

worker_selinux_annotation_value() {
    oc get numaresourcesoperator numaresourcesoperator -o json \
        | jq -r --arg mcp "${NROP_MCP_TARGET}" '
            [.spec.nodeGroups[]?
              | select(
                  .machineConfigPoolSelector.matchLabels[
                    "pools.operator.machineconfiguration.openshift.io/" + $mcp
                  ] != null
                )
              | .annotations["config.node.openshift-kni.io/selinux-policy"] // "missing"
            ] | first // "missing"'
}

assert_nrop_selinux_annotation() {
    local ann_val
    ann_val="$(worker_selinux_annotation_value)"
    if [[ "${ann_val}" != "custom" ]]; then
        echo "[FATAL] NROP CR ${NROP_MCP_TARGET} nodeGroup is missing SELinux annotation after patch! Got: ${ann_val}"
        oc get numaresourcesoperator numaresourcesoperator -o yaml
        exit 1
    fi
    echo "[VERIFY] SELinux annotation 'custom' confirmed on ${NROP_MCP_TARGET} nodeGroup"
}

assert_nrop_available() {
    local avail
    avail=$(oc get numaresourcesoperator numaresourcesoperator -o json \
        | jq -r '.status.conditions[]? | select(.type=="Available") | .status' 2>/dev/null || echo "Unknown")
    local degraded
    degraded=$(oc get numaresourcesoperator numaresourcesoperator -o json \
        | jq -r '.status.conditions[]? | select(.type=="Degraded") | .status' 2>/dev/null || echo "Unknown")
    echo "[VERIFY] NROP operator status: Available=${avail}, Degraded=${degraded}"
    if [[ "${degraded}" == "True" ]]; then
        local msg
        msg=$(oc get numaresourcesoperator numaresourcesoperator -o json \
            | jq -r '.status.conditions[]? | select(.type=="Degraded") | .message' 2>/dev/null || echo "")
        echo "[FATAL] NROP operator is Degraded: ${msg}"
        oc get numaresourcesoperator numaresourcesoperator -o yaml
        exit 1
    fi
}

assert_nrt_recreation() {
    local node_name="$1"
    local timeout="${2:-60}"

    local nrt_name=""
    for ((i=1; i<=timeout; i++)); do
        nrt_name=$(oc get noderesourcetopologies --no-headers -o custom-columns=NAME:.metadata.name 2>/dev/null \
            | grep -Fx "${node_name}" | head -1 || true)
        [[ -n "${nrt_name}" ]] && break
        sleep 1
    done

    if [[ -z "${nrt_name}" ]]; then
        echo "[FATAL] No NRT object appeared for node ${node_name} within ${timeout}s"
        return 1
    fi

    echo "[INFO] Deleting NRT '${nrt_name}' for node ${node_name} to verify RTE recreates it..."
    oc delete noderesourcetopology "${nrt_name}" --wait=true

    for ((i=1; i<=timeout; i++)); do
        local recreated
        recreated=$(oc get noderesourcetopologies --no-headers -o custom-columns=NAME:.metadata.name 2>/dev/null \
            | grep -Fx "${node_name}" || true)
        if [[ -n "${recreated}" ]]; then
            echo "[VERIFY] NRT '${recreated}' recreated for node ${node_name} after ${i}s"
            return 0
        fi
        sleep 1
    done

    echo "[FATAL] NRT was NOT recreated for node ${node_name} within ${timeout}s — RTE pod may not be functional"
    oc get pods -n openshift-numaresources --field-selector "spec.nodeName=${node_name}" -o wide 2>&1 || true
    oc get noderesourcetopologies 2>&1 || true
    exit 1
}

assert_nrt_policy() {
    local node_name="$1" max_retries="${2:-60}" delay="${3:-5}"
    local attempt
    for ((attempt=1; attempt<=max_retries; attempt++)); do
        if oc get noderesourcetopology "${node_name}" -o json 2>/dev/null | jq -e --arg scope "${TOPOLOGY_MANAGER_SCOPE}" '
            ([.attributes[]? | select(.name == "topologyManagerPolicy" and .value == "single-numa-node")] | length == 1) and
            ([.attributes[]? | select(.name == "topologyManagerScope" and .value == $scope)] | length == 1)' >/dev/null; then
            echo "[VERIFY] ${node_name}: topology policy single-numa-node, scope ${TOPOLOGY_MANAGER_SCOPE}"
            return 0
        fi
        sleep "${delay}"
    done
    echo "[FATAL] ${node_name} did not report the expected topology policy and scope"
    oc get noderesourcetopology "${node_name}" -o yaml || true
    return 1
}

assert_kubelet_runtime() {
    local node_name="$1" max_retries="${2:-60}" delay="${3:-5}"
    local attempt
    for ((attempt=1; attempt<=max_retries; attempt++)); do
        if oc get --raw "/api/v1/nodes/${node_name}/proxy/configz" 2>/dev/null | jq -e --arg scope "${TOPOLOGY_MANAGER_SCOPE}" '
            .kubeletconfig.cpuManagerPolicy == "static" and
            (.kubeletconfig.reservedSystemCPUs | type == "string" and length > 0) and
            .kubeletconfig.topologyManagerPolicy == "single-numa-node" and
            .kubeletconfig.topologyManagerScope == $scope' >/dev/null; then
            echo "[VERIFY] ${node_name}: running kubelet has static CPUs and the expected topology policy"
            return 0
        fi
        sleep "${delay}"
    done
    echo "[FATAL] ${node_name} running kubelet did not report the expected CPU and topology settings"
    return 1
}

wait_for_rte_kubelet_config() {
    local pool="$1" kubelet="$2" max_retries="${3:-60}" delay="${4:-10}"
    local attempt uid
    for ((attempt=1; attempt<=max_retries; attempt++)); do
        uid=$(oc get kubeletconfig "${kubelet}" -o jsonpath='{.metadata.uid}' --ignore-not-found 2>/dev/null || true)
        if [[ -n "${uid}" ]] && oc get configmap "numaresourcesoperator-${pool}" -n openshift-numaresources -o json 2>/dev/null |
            jq -e --arg uid "${uid}" --arg scope "${TOPOLOGY_MANAGER_SCOPE}" '
                any(.metadata.ownerReferences[]?; .uid == $uid) and
                ((.data["config.yaml"] // "") | split("\n") | map(gsub("^[[:space:]]+|[[:space:]]+$"; "")) |
                 (index("topologyManagerPolicy: single-numa-node") != null and index("topologyManagerScope: " + $scope) != null))' >/dev/null; then
            echo "[VERIFY] NROP topology ConfigMap for ${pool} matches ${kubelet}"
            return 0
        fi
        sleep "${delay}"
    done
    echo "[FATAL] NROP topology ConfigMap for ${pool} did not match ${kubelet}"
    return 1
}

wait_for_nrop_healthy() {
    local attempt max_retries="${1:-60}" delay="${2:-10}"
    for ((attempt=1; attempt<=max_retries; attempt++)); do
        if oc get numaresourcesoperator numaresourcesoperator -o json 2>/dev/null | jq -e '
            ([.status.conditions[]? | select(.type == "Available" and .status == "True")] | length == 1) and
            ([.status.conditions[]? | select(.type == "Progressing" and .status == "False")] | length == 1) and
            ([.status.conditions[]? | select(.type == "Degraded" and .status == "False")] | length == 1)' >/dev/null; then
            echo "[VERIFY] NROP is available and not progressing or degraded"
            return 0
        fi
        sleep "${delay}"
    done
    echo "[FATAL] NROP did not become healthy"
    oc get numaresourcesoperator numaresourcesoperator -o yaml || true
    return 1
}

wait_for_node_tuning_healthy() {
    local attempt
    for ((attempt=1; attempt<=60; attempt++)); do
        if oc get clusteroperator node-tuning -o json 2>/dev/null | jq -e '
            ([.status.conditions[]? | select(.type == "Available" and .status == "True")] | length == 1) and
            ([.status.conditions[]? | select(.type == "Progressing" and .status == "False")] | length == 1) and
            ([.status.conditions[]? | select(.type == "Degraded" and .status == "False")] | length == 1)' >/dev/null; then
            return 0
        fi
        sleep 10
    done
    echo "[FATAL] node-tuning did not become healthy"
    oc get clusteroperator node-tuning -o yaml || true
    return 1
}

prepare_final_worker_kubelet() {
    local backup="${ARTIFACTS_DIR}/canary-kubelet-backup.json"
    local manifest="${ARTIFACTS_DIR}/canary-final-worker-kubelet.json"
    if [[ ! -f "${manifest}" ]]; then
        if [[ -n "$(oc get kubeletconfig nrop-worker-tuning -o name --ignore-not-found)" ]]; then
            echo "[FATAL] Refusing to overwrite an existing nrop-worker-tuning"
            return 1
        fi
        oc get kubeletconfig "${MANAGED_WORKER_KUBELET}" -o json > "${backup}"
        jq -e --arg scope "${TOPOLOGY_MANAGER_SCOPE}" --arg pool "${NROP_MCP_TARGET}" '
            (.spec.kubeletConfig.cpuManagerPolicy == "static") and
            (.spec.kubeletConfig.topologyManagerPolicy == "single-numa-node") and
            (.spec.kubeletConfig.topologyManagerScope == $scope) and
            ((.spec.machineConfigPoolSelector.matchLabels == {"pools.operator.machineconfiguration.openshift.io/worker": ""}) or
             (.spec.machineConfigPoolSelector.matchLabels == {("pools.operator.machineconfiguration.openshift.io/" + $pool): ""}) or
             (.spec.machineConfigPoolSelector.matchLabels == {"nrop-ci.openshift.io/canary-kubelet": "true"}))' "${backup}" >/dev/null
        jq '{apiVersion: "machineconfiguration.openshift.io/v1", kind: "KubeletConfig",
             metadata: {name: "nrop-worker-tuning"},
             spec: (.spec + {machineConfigPoolSelector: {matchLabels: {"pools.operator.machineconfiguration.openshift.io/worker": ""}}})}' \
            "${backup}" > "${manifest}.tmp"
        mv "${manifest}.tmp" "${manifest}"
    fi
}

switch_final_worker_kubelet() {
    local backup="${ARTIFACTS_DIR}/canary-kubelet-backup.json"
    local manifest="${ARTIFACTS_DIR}/canary-final-worker-kubelet.json"
    [[ -f "${backup}" && -f "${manifest}" ]] || { echo "[FATAL] Missing KubeletConfig backup"; return 1; }
    local old_uid existing_uid
    old_uid=$(jq -r '.metadata.uid' "${backup}")
    existing_uid=$(oc get kubeletconfig "${MANAGED_WORKER_KUBELET}" -o jsonpath='{.metadata.uid}' --ignore-not-found)
    if [[ -n "${existing_uid}" && "${existing_uid}" != "${old_uid}" ]]; then
        echo "[FATAL] Temporary KubeletConfig changed identity; refusing deletion"
        return 1
    fi
    oc delete kubeletconfig "${MANAGED_WORKER_KUBELET}" --ignore-not-found --wait=true --timeout=30m
    if [[ -z "$(oc get kubeletconfig nrop-worker-tuning -o name --ignore-not-found)" ]]; then
        oc create -f "${manifest}"
    else
        oc get kubeletconfig nrop-worker-tuning -o json | jq -e --slurpfile expected "${manifest}" \
            '.spec == $expected[0].spec' >/dev/null
    fi
    oc get machineconfig -o json | jq -e --arg uid "${old_uid}" \
        'all(.items[]; all(.metadata.ownerReferences[]?; .uid != $uid))' >/dev/null
}

assert_single_ds_per_node() {
    echo "[INFO] Verifying single DaemonSet and one RTE pod per worker..."

    local ds_list
    ds_list=$(oc get daemonsets -n openshift-numaresources --no-headers \
        -o custom-columns=NAME:.metadata.name 2>/dev/null | grep "numaresourcesoperator" || true)
    local ds_count
    ds_count=$(echo "${ds_list}" | grep -c . 2>/dev/null || echo "0")

    echo "[INFO] Found ${ds_count} NROP DaemonSet(s): ${ds_list}"
    if [[ "${ds_count}" -ne 1 ]]; then
        echo "[WARNING] Expected 1 NROP DaemonSet, found ${ds_count}"
        oc get daemonsets -n openshift-numaresources -o wide 2>&1 || true
    else
        echo "[VERIFY] Single NROP DaemonSet: ${ds_list}"
    fi

    local worker_nodes
    worker_nodes=$(oc get nodes -l "node-role.kubernetes.io/${NROP_MCP_TARGET}=" --no-headers -o custom-columns=NAME:.metadata.name 2>/dev/null || true)

    for node in ${worker_nodes}; do
        local pod_count
        pod_count=$(oc get pods -n openshift-numaresources -l name=resource-topology \
            --field-selector "spec.nodeName=${node}" --no-headers 2>/dev/null | grep -c "Running" || echo "0")

        if [[ "${pod_count}" -eq 1 ]]; then
            echo "[VERIFY] Node ${node}: exactly 1 Running RTE pod"
        elif [[ "${pod_count}" -eq 0 ]]; then
            echo "[FATAL] Node ${node}: no Running RTE pod!"
            oc get pods -n openshift-numaresources --field-selector "spec.nodeName=${node}" -o wide 2>&1 || true
            exit 1
        else
            echo "[WARNING] Node ${node}: ${pod_count} Running RTE pods (expected 1)"
            oc get pods -n openshift-numaresources --field-selector "spec.nodeName=${node}" -o wide 2>&1 || true
        fi
    done
}

log_nrop_status() {
    local label="$1"
    echo "[INFO] === NROP Status Snapshot: ${label} ==="
    echo "--- NROP CR conditions ---"
    oc get numaresourcesoperator numaresourcesoperator -o json 2>/dev/null \
        | jq -r '.status.conditions[]? | "\(.type): \(.status) - \(.message // "n/a")"' || true
    echo "--- NROP DaemonSets in CR status ---"
    oc get numaresourcesoperator numaresourcesoperator -o json 2>/dev/null \
        | jq -r '.status.daemonsets[]? | .name' || echo "(none)"
    echo "--- NROP MCPs in CR status ---"
    oc get numaresourcesoperator numaresourcesoperator -o json 2>/dev/null \
        | jq -r '.status.machineconfigpools[]? | .name' || echo "(none)"
    oc get numaresourcesoperator numaresourcesoperator -o yaml > "${ARTIFACTS_DIR}/nrop-cr-status-${label}.yaml" 2>/dev/null || true
    echo "[INFO] === End NROP Status Snapshot ==="
}

collect_migration_summary() {
    local label="${1:-final}"
    echo ""
    echo "[INFO] ============================================="
    echo "[INFO] === MIGRATION SUMMARY (${label}) ==="
    echo "[INFO] ============================================="

    echo ""
    echo "--- Node versions ---"
    oc get nodes -o custom-columns=NAME:.metadata.name,STATUS:.status.conditions[-1].type,VERSION:.status.nodeInfo.kubeletVersion,OS:.status.nodeInfo.osImage -o wide 2>&1 || true

    echo ""
    echo "--- MachineConfigPools ---"
    oc get mcp -o wide 2>&1 || true

    echo ""
    echo "--- NROP DaemonSets ---"
    oc get daemonsets -n openshift-numaresources -o wide 2>&1 || true

    echo ""
    echo "--- NROP Pods ---"
    oc get pods -n openshift-numaresources -o wide 2>&1 || true

    echo ""
    log_nrop_status "${label}"

    echo ""
    echo "[INFO] ============================================="
    echo "[INFO] === END MIGRATION SUMMARY ==="
    echo "[INFO] ============================================="
}

temporary_nodegroup_config_line() {
    if [[ -z "${NROP_TEMP_NODEGROUP_CONFIG_JSON}" ]]; then
        return 0
    fi
    local config
    config=$(jq -c -e 'if type == "object" and .podsFingerprinting == "Enabled" then . else error("invalid temporary node-group config") end' <<< "${NROP_TEMP_NODEGROUP_CONFIG_JSON}")
    printf '    config: %s' "${config}"
}

phase_setup() {
    echo "[INFO] === CANARY SETUP PHASE ==="
    local nodegroup_config
    nodegroup_config=$(temporary_nodegroup_config_line)

    echo "[INFO] Step 1: Creating ${UPGRADE_MCP_NAME} MachineConfigPool"
    cat <<EOF | oc apply -f -
apiVersion: machineconfiguration.openshift.io/v1
kind: MachineConfigPool
metadata:
  name: ${UPGRADE_MCP_NAME}
  labels:
    pools.operator.machineconfiguration.openshift.io/${UPGRADE_MCP_NAME}: ""
spec:
  machineConfigSelector:
    matchExpressions:
      - key: machineconfiguration.openshift.io/role
        operator: In
        values:
          - worker
          - ${UPGRADE_MCP_NAME}
  nodeSelector:
    matchLabels:
      node-role.kubernetes.io/${UPGRADE_MCP_NAME}: ""
EOF
    echo "[INFO] MCP ${UPGRADE_MCP_NAME} created"
    oc get mcp "${UPGRADE_MCP_NAME}" -o yaml > "${ARTIFACTS_DIR}/mcp-${UPGRADE_MCP_NAME}.yaml" || true

    if ! oc get mcp "${UPGRADE_MCP_NAME}" &>/dev/null; then
        echo "[FATAL] MCP ${UPGRADE_MCP_NAME} was not created!"
        oc get mcp -o wide
        exit 1
    fi
    local mcp_label
    mcp_label=$(oc get mcp "${UPGRADE_MCP_NAME}" -o json \
        | jq -r ".metadata.labels[\"pools.operator.machineconfiguration.openshift.io/${UPGRADE_MCP_NAME}\"] // \"missing\"")
    if [[ "${mcp_label}" == "missing" ]]; then
        echo "[FATAL] MCP ${UPGRADE_MCP_NAME} is missing its pools.operator label!"
        oc get mcp "${UPGRADE_MCP_NAME}" -o yaml
        exit 1
    fi
    echo "[VERIFY] MCP ${UPGRADE_MCP_NAME} created with correct pools.operator label"

    echo "[INFO] Step 2: Adding ${UPGRADE_MCP_NAME} nodeGroup to NROP CR"
    cat <<EOF > "${ARTIFACTS_DIR}/nrop-cr-setup.yaml"
apiVersion: nodetopology.openshift.io/v1
kind: NUMAResourcesOperator
metadata:
  name: numaresourcesoperator
spec:
  nodeGroups:
  - machineConfigPoolSelector:
      matchLabels:
        pools.operator.machineconfiguration.openshift.io/${NROP_MCP_TARGET}: ""
${nodegroup_config}
  - machineConfigPoolSelector:
      matchLabels:
        pools.operator.machineconfiguration.openshift.io/${UPGRADE_MCP_NAME}: ""
${nodegroup_config}
EOF
    oc apply -f "${ARTIFACTS_DIR}/nrop-cr-setup.yaml"
    assert_nrop_upgrade_nodegroup
    assert_nrop_available

    oc get numaresourcesoperator numaresourcesoperator -o yaml > "${ARTIFACTS_DIR}/nrop-cr-after-setup.yaml" || true

    echo "[INFO] Step 3: Adding pause-reconciliation annotation to NROP CR"
    oc annotate numaresourcesoperator numaresourcesoperator \
        config.numa-operator.openshift.io/pause-reconciliation=enabled --overwrite
    local pause_val
    pause_val=$(oc get numaresourcesoperator numaresourcesoperator -o json \
        | jq -r '.metadata.annotations["config.numa-operator.openshift.io/pause-reconciliation"] // "missing"')
    if [[ "${pause_val}" != "enabled" ]]; then
        echo "[FATAL] pause-reconciliation annotation was not applied! Expected: enabled, Got: ${pause_val}"
        oc get numaresourcesoperator numaresourcesoperator -o yaml
        exit 1
    fi
    echo "[VERIFY] pause-reconciliation annotation set to 'enabled'"

    if [[ -n "${OCP_TARGET_VERSION:-}" ]]; then
        echo "[INFO] Setting update channel to eus-${OCP_TARGET_VERSION}"
        oc adm upgrade channel "eus-${OCP_TARGET_VERSION}"

        local actual_channel
        actual_channel=$(oc get clusterversion version -o jsonpath='{.spec.channel}' 2>/dev/null || echo "")
        if [[ "${actual_channel}" != "eus-${OCP_TARGET_VERSION}" ]]; then
            echo "[FATAL] EUS channel was not set! Expected: eus-${OCP_TARGET_VERSION}, Got: ${actual_channel}"
            oc get clusterversion version -o yaml
            exit 1
        fi
        echo "[VERIFY] Update channel set to ${actual_channel}"
    else
        echo "[WARNING] OCP_TARGET_VERSION not set, skipping EUS channel configuration"
    fi

    echo "[INFO] Step 4: Pausing ${NROP_MCP_TARGET} MCP"
    oc patch mcp/"${NROP_MCP_TARGET}" --type merge --patch '{"spec":{"paused":true}}'

    local paused
    paused=$(oc get mcp "${NROP_MCP_TARGET}" -o jsonpath='{.spec.paused}' 2>/dev/null || echo "false")
    if [[ "${paused}" != "true" ]]; then
        echo "[FATAL] MCP ${NROP_MCP_TARGET} is not paused after patch! Got: ${paused}"
        oc get mcp "${NROP_MCP_TARGET}" -o yaml
        exit 1
    fi
    echo "[VERIFY] MCP ${NROP_MCP_TARGET} paused successfully"

    oc get mcp -o wide
    echo "[INFO] === CANARY SETUP PHASE COMPLETE ==="
    echo "[INFO] Next: Upgrade control plane (Steps 5), then run 'migrate' phase"
}

phase_migrate() {
    echo "[INFO] === CANARY MIGRATE WORKERS PHASE ==="
    local nodegroup_config
    nodegroup_config=$(temporary_nodegroup_config_line)

    log_nrop_status "migrate-start"

    if [[ "${OCP_FROM_MINOR}" -lt 18 ]]; then
        echo "[INFO] Step 9: Adding custom SELinux annotation to worker nodeGroup (upgrading from 4.${OCP_FROM_MINOR}, pre-4.18)"
        cat <<EOF > "${ARTIFACTS_DIR}/nrop-cr-migrate.yaml"
apiVersion: nodetopology.openshift.io/v1
kind: NUMAResourcesOperator
metadata:
  name: numaresourcesoperator
spec:
  nodeGroups:
  - machineConfigPoolSelector:
      matchLabels:
        pools.operator.machineconfiguration.openshift.io/${NROP_MCP_TARGET}: ""
    annotations:
      config.node.openshift-kni.io/selinux-policy: "custom"
${nodegroup_config}
  - machineConfigPoolSelector:
      matchLabels:
        pools.operator.machineconfiguration.openshift.io/${UPGRADE_MCP_NAME}: ""
${nodegroup_config}
EOF
        oc apply -f "${ARTIFACTS_DIR}/nrop-cr-migrate.yaml"
        assert_nrop_selinux_annotation
    else
        echo "[INFO] Step 9: Skipping SELinux annotation (source 4.${OCP_FROM_MINOR} and target share the same built-in SELinux policy)"
    fi

    echo "[INFO] Step 10: Removing pause-reconciliation annotation from NROP CR"
    oc annotate numaresourcesoperator numaresourcesoperator \
        config.numa-operator.openshift.io/pause-reconciliation- --overwrite
    local pause_val
    pause_val=$(oc get numaresourcesoperator numaresourcesoperator -o json \
        | jq -r '.metadata.annotations["config.numa-operator.openshift.io/pause-reconciliation"] // "removed"')
    if [[ "${pause_val}" != "removed" ]]; then
        echo "[FATAL] pause-reconciliation annotation was not removed! Got: ${pause_val}"
        oc get numaresourcesoperator numaresourcesoperator -o yaml
        exit 1
    fi
    echo "[VERIFY] pause-reconciliation annotation removed"

    assert_nrop_upgrade_nodegroup
    assert_nrop_available

    if [[ -n "${MANAGED_CANARY_PROFILE}" ]]; then
        wait_for_rte_kubelet_config "${NROP_MCP_TARGET}" "performance-${NROP_MCP_TARGET}-performance-nrop" 60 10
        wait_for_rte_kubelet_config "${UPGRADE_MCP_NAME}" "performance-${MANAGED_CANARY_PROFILE}" 60 10
    elif [[ -n "${MANAGED_WORKER_KUBELET}" && -n "${MANAGED_CANARY_KUBELET}" ]]; then
        wait_for_rte_kubelet_config "${NROP_MCP_TARGET}" "${MANAGED_WORKER_KUBELET}" 60 10
        wait_for_rte_kubelet_config "${UPGRADE_MCP_NAME}" "${MANAGED_CANARY_KUBELET}" 60 10
    fi

    oc get numaresourcesoperator numaresourcesoperator -o yaml > "${ARTIFACTS_DIR}/nrop-cr-after-verify.yaml" || true

    # Worker MCP is paused (Step 4), so the SELinux MachineConfig won't be applied yet.
    # Skip waiting — nodes will pick up the config when they migrate to worker-upgrade MCP.
    echo "[INFO] Worker MCP is paused — skipping MCP stabilization wait (SELinux MC will apply during node migration)"

    local worker_nodes
    worker_nodes=$(oc get nodes -l "node-role.kubernetes.io/${NROP_MCP_TARGET}=" --no-headers -o custom-columns=NAME:.metadata.name)

    if [[ -z "${worker_nodes}" ]]; then
        echo "[ERROR] No worker nodes found with label node-role.kubernetes.io/${NROP_MCP_TARGET}"
        exit 1
    fi

    local total_nodes
    total_nodes=$(echo "${worker_nodes}" | wc -l)

    local node_count="${total_nodes}"
    if [[ "${CANARY_NODE_COUNT}" -gt 0 && "${CANARY_NODE_COUNT}" -lt "${total_nodes}" ]]; then
        node_count="${CANARY_NODE_COUNT}"
        echo "[INFO] CANARY_NODE_COUNT=${CANARY_NODE_COUNT}: migrating ${node_count} of ${total_nodes} worker node(s)"
    fi
    echo "[INFO] Found ${total_nodes} worker node(s), will migrate ${node_count}: ${worker_nodes}"

    local current=0
    for node in ${worker_nodes}; do
        if [[ "${current}" -ge "${node_count}" ]]; then
            echo "[INFO] Reached CANARY_NODE_COUNT=${node_count}, skipping remaining nodes"
            break
        fi
        current=$((current + 1))
        echo "[INFO] === Migrating node ${current}/${node_count}: ${node} ==="

        if oc get node "${node}" -o jsonpath="{.metadata.labels}" | jq -e ".[\"node-role.kubernetes.io/${UPGRADE_MCP_NAME}\"]" > /dev/null 2>&1; then
            echo "[INFO] Node ${node} already has ${UPGRADE_MCP_NAME} label, skipping migration"
            assert_rte_pod_running_on_node "${node}"
            assert_rte_pod_ready_for_mcp "${UPGRADE_MCP_NAME}" "${node}"
            assert_rte_daemonset_status "${node}"
            assert_rte_daemonset_for_mcp "${UPGRADE_MCP_NAME}"
            continue
        fi

        collect_nrop_operator_logs "before-${node}"

        echo "[INFO] Step 11: Moving node ${node} to ${UPGRADE_MCP_NAME} MCP"
        move_worker_to_upgrade "${node}"

        echo "[INFO] Waiting for ${UPGRADE_MCP_NAME} MCP to begin updating"
        sleep 30

        echo "[INFO] Waiting for node ${node} to become Ready after upgrade"
        wait_for_node_ready "${node}" 120 30

        echo "[INFO] Waiting for ${UPGRADE_MCP_NAME} MCP to stabilize"
        wait_for_mcp_stable "${UPGRADE_MCP_NAME}" 120 30

        echo "[INFO] Verifying RTE pod on migrated node ${node}"
        assert_rte_pod_running_on_node "${node}"
        assert_rte_pod_ready_for_mcp "${UPGRADE_MCP_NAME}" "${node}"
        assert_rte_daemonset_status "${node}"
        assert_rte_daemonset_for_mcp "${UPGRADE_MCP_NAME}"
        assert_nrt_recreation "${node}"
        assert_nrt_policy "${node}"
        assert_kubelet_runtime "${node}"
        collect_nrop_operator_logs "after-${node}"

        echo "[INFO] Verifying RTE pods on non-migrated nodes"
        for other_node in ${worker_nodes}; do
            if [[ "${other_node}" == "${node}" ]]; then
                continue
            fi
            if oc get node "${other_node}" -o jsonpath="{.metadata.labels}" \
                | jq -e ".[\"node-role.kubernetes.io/${UPGRADE_MCP_NAME}\"]" > /dev/null 2>&1; then
                continue
            fi
            echo "[INFO] Checking non-migrated node ${other_node}"
            assert_rte_pod_running_on_node "${other_node}" 5 10
            assert_nrt_recreation "${other_node}"
            assert_nrt_policy "${other_node}"
            assert_kubelet_runtime "${other_node}"
        done

        oc get nodes -o wide
        oc get mcp -o wide
        echo "[INFO] Node ${node} migrated and verified successfully (${current}/${node_count})"
    done

    wait_for_nrop_healthy 60 10
    collect_migration_summary "migrate-end"
    echo "[INFO] === CANARY MIGRATE WORKERS PHASE COMPLETE ==="
}

phase_cleanup() {
    echo "[INFO] === CANARY CLEANUP PHASE ==="
    local nodegroup_config
    nodegroup_config=$(temporary_nodegroup_config_line)

    if [[ "${OCP_FROM_MINOR}" -lt 18 ]]; then
        echo "[INFO] Step 13: Removing custom SELinux annotation from NROP CR worker nodeGroup (was required for pre-4.18 source)"
        cat <<EOF > "${ARTIFACTS_DIR}/nrop-cr-cleanup-selinux.yaml"
apiVersion: nodetopology.openshift.io/v1
kind: NUMAResourcesOperator
metadata:
  name: numaresourcesoperator
spec:
  nodeGroups:
  - machineConfigPoolSelector:
      matchLabels:
        pools.operator.machineconfiguration.openshift.io/${NROP_MCP_TARGET}: ""
${nodegroup_config}
  - machineConfigPoolSelector:
      matchLabels:
        pools.operator.machineconfiguration.openshift.io/${UPGRADE_MCP_NAME}: ""
${nodegroup_config}
EOF
        oc apply -f "${ARTIFACTS_DIR}/nrop-cr-cleanup-selinux.yaml"

        local ann_after
        ann_after="$(worker_selinux_annotation_value)"
        if [[ "${ann_after}" != "missing" ]]; then
            echo "[FATAL] SELinux annotation was NOT removed from NROP CR ${NROP_MCP_TARGET} nodeGroup! Got: ${ann_after}"
            oc get numaresourcesoperator numaresourcesoperator -o yaml
            exit 1
        fi
        echo "[VERIFY] SELinux annotation removed from NROP CR worker nodeGroup"
    else
        echo "[INFO] Step 13: Skipping SELinux annotation removal (not added for upgrades from 4.${OCP_FROM_MINOR}+)"
    fi

    echo "[INFO] Step 14: Moving all nodes back to ${NROP_MCP_TARGET} MCP"
    local upgrade_nodes
    upgrade_nodes=$(oc get nodes -l "node-role.kubernetes.io/${UPGRADE_MCP_NAME}=" --no-headers -o custom-columns=NAME:.metadata.name 2>/dev/null || true)

    if [[ -n "${upgrade_nodes}" ]]; then
        for node in ${upgrade_nodes}; do
            echo "[INFO] Returning ${node} to ${NROP_MCP_TARGET}"
            return_worker_to_regular "${node}"
        done
        echo "[INFO] All nodes moved back to ${NROP_MCP_TARGET} MCP"
    else
        echo "[INFO] No nodes found in ${UPGRADE_MCP_NAME} MCP"
    fi

    local expected_workers
    expected_workers=$(oc get nodes -l "node-role.kubernetes.io/${NROP_MCP_TARGET}=" --no-headers 2>/dev/null | wc -l)
    echo "[INFO] Expecting ${expected_workers} worker node(s) in ${NROP_MCP_TARGET} MCP"

    echo "[INFO] Step 15: Unpausing ${NROP_MCP_TARGET} MCP"
    oc patch mcp/"${NROP_MCP_TARGET}" --type merge --patch '{"spec":{"paused":false}}'
    echo "[INFO] MCP ${NROP_MCP_TARGET} unpaused — nodes will reboot to reconcile config"

    echo "[INFO] Waiting for ${NROP_MCP_TARGET} MCP to stabilize with all ${expected_workers} worker(s)"
    wait_for_mcp_stable "${NROP_MCP_TARGET}" 120 30 "${expected_workers}"
    # The upgrade pool owns its rendered configs. All nodes must stop
    # referencing them before the pool is deleted.
    oc get nodes -l 'node-role.kubernetes.io/worker=' -o json | jq -e --arg upgrade "rendered-${UPGRADE_MCP_NAME}-" '
        all(.items[];
            .metadata.annotations["machineconfiguration.openshift.io/state"] == "Done" and
            .metadata.annotations["machineconfiguration.openshift.io/currentConfig"] == .metadata.annotations["machineconfiguration.openshift.io/desiredConfig"] and
            ((.metadata.annotations["machineconfiguration.openshift.io/currentConfig"] | startswith($upgrade)) | not))' >/dev/null

    echo "[INFO] Waiting for NROP pods to stabilize after MCP reconciliation"
    local max_retries=40
    local delay=15
    for ((i=1; i<=max_retries; i++)); do
        local not_running
        not_running=$(oc get pods -n openshift-numaresources --no-headers 2>/dev/null \
            | grep -c -v -E "Running|Completed" || true)
        if [[ "${not_running}" -eq 0 ]]; then
            echo "[INFO] All NROP pods are in Running/Completed state"
            break
        fi
        echo "[INFO] ${not_running} NROP pod(s) not yet Running/Completed (attempt ${i}/${max_retries})"
        if [[ "${i}" == "${max_retries}" ]]; then
            echo "[WARNING] NROP pods did not fully stabilize within $((max_retries * delay / 60)) min"
            oc get pods -n openshift-numaresources -o wide
        fi
        sleep "${delay}"
    done

    oc get pods -n openshift-numaresources -o wide

    local worker_nodes
    worker_nodes=$(oc get nodes -l "node-role.kubernetes.io/${NROP_MCP_TARGET}=" --no-headers -o custom-columns=NAME:.metadata.name 2>/dev/null || true)
    for node in ${worker_nodes}; do
        assert_rte_pod_running_on_node "${node}" 20 15
    done

    assert_nrop_available

    echo "[INFO] Verifying end state: single DaemonSet, one RTE pod per worker"
    assert_single_ds_per_node

    echo "[INFO] Verifying NRT recreation on all worker nodes"
    for node in ${worker_nodes}; do
        assert_nrt_recreation "${node}"
    done

    echo "[INFO] Step 16: Removing ${UPGRADE_MCP_NAME} nodeGroup from NROP CR and deleting MCP"
    cat <<EOF > "${ARTIFACTS_DIR}/nrop-cr-final.yaml"
apiVersion: nodetopology.openshift.io/v1
kind: NUMAResourcesOperator
metadata:
  name: numaresourcesoperator
spec:
  nodeGroups:
  - machineConfigPoolSelector:
      matchLabels:
        pools.operator.machineconfiguration.openshift.io/${NROP_MCP_TARGET}: ""
${nodegroup_config}
EOF
    oc apply -f "${ARTIFACTS_DIR}/nrop-cr-final.yaml"

    local remaining
    remaining=$(oc get numaresourcesoperator numaresourcesoperator -o json \
        | jq -r --arg mcp "${UPGRADE_MCP_NAME}" \
          '[.spec.nodeGroups // [] | .[] | select(.machineConfigPoolSelector.matchLabels["pools.operator.machineconfiguration.openshift.io/" + $mcp] != null)] | length')
    if [[ "${remaining}" != "0" ]]; then
        echo "[FATAL] ${UPGRADE_MCP_NAME} nodeGroup was NOT removed from NROP CR!"
        oc get numaresourcesoperator numaresourcesoperator -o yaml
        exit 1
    fi
    echo "[VERIFY] ${UPGRADE_MCP_NAME} nodeGroup removed from NROP CR"

    if [[ -n "${MANAGED_CANARY_PROFILE}" && -n "$(oc get performanceprofile "${MANAGED_CANARY_PROFILE}" -o name --ignore-not-found)" ]]; then
        local managed_label
        managed_label=$(oc get performanceprofile "${MANAGED_CANARY_PROFILE}" -o json \
            | jq -r '.metadata.labels["nrop-ci.openshift.io/canary-managed"] // ""')
        if [[ "${managed_label}" != "true" ]]; then
            echo "[FATAL] Refusing to delete an unowned canary PerformanceProfile: ${MANAGED_CANARY_PROFILE}"
            exit 1
        fi
        oc delete performanceprofile "${MANAGED_CANARY_PROFILE}" --wait=true
        echo "[VERIFY] Deleted the managed canary PerformanceProfile"
    fi

    if [[ -n "${MANAGED_CANARY_KUBELET}" && -n "$(oc get kubeletconfig "${MANAGED_CANARY_KUBELET}" -o name --ignore-not-found)" ]]; then
        oc get kubeletconfig "${MANAGED_CANARY_KUBELET}" -o json | jq -e --arg pool "${UPGRADE_MCP_NAME}" '
            .metadata.labels["nrop-ci.openshift.io/canary-managed"] == "true" and
            .spec.machineConfigPoolSelector.matchLabels == {("pools.operator.machineconfiguration.openshift.io/" + $pool): ""}' >/dev/null
        oc delete kubeletconfig "${MANAGED_CANARY_KUBELET}" --wait=true --timeout=30m
        echo "[VERIFY] Deleted the managed canary KubeletConfig"
    fi

    echo "[INFO] Deleting ${UPGRADE_MCP_NAME} MCP"
    oc delete mcp "${UPGRADE_MCP_NAME}" --ignore-not-found=true
    echo "[INFO] MCP ${UPGRADE_MCP_NAME} deleted"

    oc get numaresourcesoperator numaresourcesoperator -o yaml > "${ARTIFACTS_DIR}/nrop-cr-after-cleanup.yaml" || true

    echo "[INFO] Waiting for NROP pods to settle after nodeGroup removal"
    for ((i=1; i<=20; i++)); do
        local not_running
        not_running=$(oc get pods -n openshift-numaresources --no-headers 2>/dev/null \
            | grep -c -v -E "Running|Completed" || true)
        if [[ "${not_running}" -eq 0 ]]; then
            echo "[INFO] All NROP pods are in Running/Completed state"
            break
        fi
        echo "[INFO] ${not_running} NROP pod(s) not yet Running/Completed (attempt ${i}/20)"
        sleep 15
    done

    echo "[INFO] Final verification: single DaemonSet, all pods Running"
    local final_ds_count
    final_ds_count=$(oc get daemonsets -n openshift-numaresources --no-headers \
        -o custom-columns=NAME:.metadata.name 2>/dev/null | grep -c "numaresourcesoperator" || echo "0")
    if [[ "${final_ds_count}" -ne 1 ]]; then
        echo "[FATAL] Expected 1 NROP DaemonSet after cleanup, found ${final_ds_count}"
        oc get daemonsets -n openshift-numaresources -o wide 2>&1 || true
        exit 1
    fi
    echo "[VERIFY] Single NROP DaemonSet confirmed after full cleanup"

    local bad_pods
    bad_pods=$(oc get pods -n openshift-numaresources --no-headers 2>/dev/null \
        | grep -v -E "Running|Completed" || true)
    if [[ -n "${bad_pods}" ]]; then
        echo "[FATAL] NROP pods not all in Running/Completed state after cleanup:"
        echo "${bad_pods}"
        oc get pods -n openshift-numaresources -o wide 2>&1 || true
        exit 1
    fi
    echo "[VERIFY] All NROP pods are Running/Completed"

    oc get pods -n openshift-numaresources -o wide
    oc get mcp -o wide
    oc get nodes -o wide
    echo "[INFO] === CANARY CLEANUP PHASE COMPLETE ==="
}

# Run separately from cleanup so a partial normalization can be retried using
# the saved profile manifest, without repeating the node migration phase.
phase_normalize() {
    local expected_workers nodes node regular_profile final_profile backup final_manifest
    local final_worker_paused=false
    regular_profile="${NROP_MCP_TARGET}-performance-nrop"
    final_profile="worker-performance-nrop"
    backup="${ARTIFACTS_DIR}/canary-regular-profile-backup.json"
    final_manifest="${ARTIFACTS_DIR}/canary-final-worker-profile.json"

    if [[ -n "$(oc get mcp "${UPGRADE_MCP_NAME}" -o name --ignore-not-found)" ]]; then
        echo "[FATAL] Refusing normalization while ${UPGRADE_MCP_NAME} still exists"
        return 1
    fi
    nodes=$(oc get nodes -l 'node-role.kubernetes.io/worker=' -o json)
    expected_workers=$(jq '.items | length' <<< "${nodes}")
    if [[ "${expected_workers}" -lt 1 ]] || ! jq -e '
        all(.items[]; any(.status.conditions[]?; .type == "Ready" and .status == "True"))' <<< "${nodes}" >/dev/null; then
        echo "[FATAL] Expected ready workers before normalization"
        return 1
    fi

    if [[ -z "${MANAGED_CANARY_PROFILE}" ]]; then
        [[ -n "${MANAGED_WORKER_KUBELET}" ]] || { echo "[FATAL] No managed KubeletConfig specified"; return 1; }
        prepare_final_worker_kubelet
    fi

    if [[ "${NROP_MCP_TARGET}" != "worker" ]]; then
        if [[ -n "${MANAGED_CANARY_PROFILE}" ]] && ! oc get mcp -o json | jq -e --arg regular "${NROP_MCP_TARGET}" \
            'all(.items[]; .metadata.name == "master" or .metadata.name == "worker" or .metadata.name == $regular)' >/dev/null; then
            echo "[FATAL] Other custom pools exist; a worker PerformanceProfile could match them"
            return 1
        fi
        if [[ -n "${MANAGED_CANARY_PROFILE}" && ! -f "${final_manifest}" ]]; then
            if [[ -n "$(oc get performanceprofile "${final_profile}" -o name --ignore-not-found)" ]]; then
                echo "[FATAL] Refusing to overwrite an existing ${final_profile}"
                return 1
            fi
            oc get performanceprofile "${regular_profile}" -o json > "${backup}"
            jq -e --arg pool "${NROP_MCP_TARGET}" '
                .spec.nodeSelector == {("node-role.kubernetes.io/" + $pool): ""} and
                .spec.machineConfigPoolSelector == {("pools.operator.machineconfiguration.openshift.io/" + $pool): ""}' "${backup}" >/dev/null
            jq --arg name "${final_profile}" '
                {apiVersion: "performance.openshift.io/v2", kind: "PerformanceProfile",
                 metadata: {name: $name, annotations: ((.metadata.annotations // {}) | with_entries(select(.key == "kubeletconfig.experimental")))},
                 spec: (.spec + {nodeSelector: {"node-role.kubernetes.io/worker": ""},
                   machineConfigPoolSelector: {"pools.operator.machineconfiguration.openshift.io/worker": ""},
                   machineConfigLabel: {"machineconfiguration.openshift.io/role": "worker"}})}' "${backup}" > "${final_manifest}.tmp"
            mv "${final_manifest}.tmp" "${final_manifest}"
        fi

        if [[ -n "$(oc get mcp "${NROP_MCP_TARGET}" -o name --ignore-not-found)" ]]; then
            local current_cr json_patch worker_group_patch
            if [[ -n "${NROP_ORIGINAL_NODEGROUP_CONFIG_JSON}" ]]; then
                worker_group_patch=$(jq -cn --argjson config "${NROP_ORIGINAL_NODEGROUP_CONFIG_JSON}" \
                    'if ($config | type) != "object" then error("invalid original node-group config") else {spec:{nodeGroups:[{machineConfigPoolSelector:{matchLabels:{"pools.operator.machineconfiguration.openshift.io/worker":""}},config:$config}]}} end')
            else
                worker_group_patch='{"spec":{"nodeGroups":[{"machineConfigPoolSelector":{"matchLabels":{"pools.operator.machineconfiguration.openshift.io/worker":""}}}]}}'
            fi
            if [[ -n "${NROP_TEMP_NODEGROUP_CONFIG_JSON}" ]]; then
                current_cr=$(oc get numaresourcesoperator numaresourcesoperator -o json)
                if ! jq -e --arg uid "${NROP_FINGERPRINT_CR_UID}" --arg pool "${NROP_MCP_TARGET}" \
                    --argjson config "${NROP_TEMP_NODEGROUP_CONFIG_JSON}" --argjson target "${worker_group_patch}" '
                    $uid != "" and .metadata.uid == $uid and (.spec.nodeGroups | length) == 1 and
                    ((.spec.nodeGroups[0].machineConfigPoolSelector.matchLabels["pools.operator.machineconfiguration.openshift.io/" + $pool] == "" and
                      .spec.nodeGroups[0].config == $config) or .spec.nodeGroups == $target.spec.nodeGroups)' <<< "${current_cr}" >/dev/null; then
                    echo "[FATAL] NROP identity or temporary configuration changed; refusing normalization"
                    return 1
                fi
            fi
            oc patch mcp "${NROP_MCP_TARGET}" --type merge --patch '{"spec":{"paused":true}}'

            if [[ -n "${MANAGED_CANARY_PROFILE}" ]]; then
                if [[ ! -f "${final_manifest}" ]]; then
                    echo "[FATAL] Missing saved worker profile manifest"
                    return 1
                fi
                local saved_uid current_uid
                saved_uid=$(jq -r '.metadata.uid' "${backup}")
                current_uid=$(oc get performanceprofile "${regular_profile}" -o jsonpath='{.metadata.uid}' --ignore-not-found)
                if [[ -n "${current_uid}" && "${current_uid}" != "${saved_uid}" ]]; then
                    echo "[FATAL] Regular PerformanceProfile changed identity; refusing deletion"
                    return 1
                fi
                oc delete performanceprofile "${regular_profile}" --ignore-not-found --wait=true
            elif [[ -n "${MANAGED_WORKER_KUBELET}" ]]; then
                switch_final_worker_kubelet
            else
                echo "[FATAL] No managed tuning specified for normalization"
                return 1
            fi

            if [[ -n "${NROP_TEMP_NODEGROUP_CONFIG_JSON}" ]]; then
                json_patch=$(jq -cn --arg uid "${NROP_FINGERPRINT_CR_UID}" \
                    --argjson old "$(jq -c '.spec.nodeGroups' <<< "${current_cr}")" \
                    --argjson replacement "$(jq -c '.spec.nodeGroups' <<< "${worker_group_patch}")" \
                    '[{op:"test",path:"/metadata/uid",value:$uid},{op:"test",path:"/spec/nodeGroups",value:$old},{op:"replace",path:"/spec/nodeGroups",value:$replacement}]')
                oc patch numaresourcesoperator numaresourcesoperator --type json -p "${json_patch}"
            else
                oc patch numaresourcesoperator numaresourcesoperator --type merge -p "${worker_group_patch}"
            fi
            for node in $(jq -r --arg role "node-role.kubernetes.io/${NROP_MCP_TARGET}" '.items[] | select(.metadata.labels[$role] != null) | .metadata.name' <<< "${nodes}"); do
                oc label node "${node}" "node-role.kubernetes.io/${NROP_MCP_TARGET}-" --overwrite
            done

            local attempt count
            for ((attempt=1; attempt<=120; attempt++)); do
                count=$(oc get mcp "${NROP_MCP_TARGET}" -o jsonpath='{.status.machineCount}')
                [[ "${count}" == "0" ]] && break
                sleep 5
            done
            if [[ "${count}" != "0" ]]; then
                echo "[FATAL] ${NROP_MCP_TARGET} is not empty; refusing to delete it"
                return 1
            fi
            # The MCO still needs each node's current rendered config while
            # moving it to worker. Deleting its owning pool first garbage
            # collects that config and degrades the nodes.
            wait_for_mcp_stable worker 120 30 "${expected_workers}"
            oc get nodes -l 'node-role.kubernetes.io/worker=' -o json | jq -e --arg regular "rendered-${NROP_MCP_TARGET}-" '
                all(.items[];
                    .metadata.annotations["machineconfiguration.openshift.io/state"] == "Done" and
                    .metadata.annotations["machineconfiguration.openshift.io/currentConfig"] == .metadata.annotations["machineconfiguration.openshift.io/desiredConfig"] and
                    ((.metadata.annotations["machineconfiguration.openshift.io/currentConfig"] | startswith($regular)) | not))' >/dev/null
            oc delete mcp "${NROP_MCP_TARGET}" --wait=true
        elif [[ -z "${MANAGED_CANARY_PROFILE}" ]]; then
            # Resume safely if the temporary pool was already deleted.
            oc patch mcp worker --type merge --patch '{"spec":{"paused":true}}'
            final_worker_paused=true
            switch_final_worker_kubelet
        fi

        if [[ -n "${MANAGED_CANARY_PROFILE}" ]]; then
            if [[ -z "$(oc get performanceprofile "${final_profile}" -o name --ignore-not-found)" ]]; then
                oc create -f "${final_manifest}"
            else
                oc get performanceprofile "${final_profile}" -o json | jq -e --slurpfile expected "${final_manifest}" \
                    '.spec == $expected[0].spec' >/dev/null
            fi
            oc wait --for=condition=Available "performanceprofile/${final_profile}" --timeout=30m
        fi
    elif [[ -z "${MANAGED_CANARY_PROFILE}" ]]; then
        oc patch mcp worker --type merge --patch '{"spec":{"paused":true}}'
        final_worker_paused=true
        switch_final_worker_kubelet
    fi

    local kubelet_name kubelet_uid generated_mc
    if [[ -n "${MANAGED_CANARY_PROFILE}" ]]; then
        kubelet_name="performance-${final_profile}"
    else
        kubelet_name="nrop-worker-tuning"
    fi
    [[ -n "${kubelet_name}" ]] || { echo "[FATAL] No final worker tuning specified"; return 1; }
    local attempt
    for ((attempt=1; attempt<=180; attempt++)); do
        kubelet_uid=$(oc get kubeletconfig "${kubelet_name}" -o jsonpath='{.metadata.uid}' --ignore-not-found 2>/dev/null || true)
        if [[ -z "${kubelet_uid}" ]]; then
            sleep 10
            continue
        fi
        generated_mc=$(oc get machineconfig -o json | jq -r --arg uid "${kubelet_uid}" '
            [.items[] | select(.metadata.labels["machineconfiguration.openshift.io/role"] == "worker")
             | select(any(.metadata.ownerReferences[]?; .uid == $uid)) | .metadata.name] | first // ""')
        if [[ -n "${generated_mc}" ]] && oc get mcp worker -o json | jq -e --arg mc "${generated_mc}" \
            'any(.spec.configuration.source[]?; .name == $mc)' >/dev/null; then
            break
        fi
        sleep 10
    done
    [[ -n "${generated_mc}" ]] && oc get mcp worker -o json | jq -e --arg mc "${generated_mc}" \
        'any(.spec.configuration.source[]?; .name == $mc)' >/dev/null
    if [[ "${final_worker_paused}" == "true" ]]; then
        oc patch mcp worker --type merge --patch '{"spec":{"paused":false}}'
    fi
    wait_for_mcp_stable worker 120 30 "${expected_workers}"
    oc get mcp worker -o json | jq -e --argjson expected "${expected_workers}" '
        .spec.paused != true and .status.machineCount == $expected and
        .status.readyMachineCount == $expected and .status.updatedMachineCount == $expected' >/dev/null
    wait_for_nrop_healthy 60 10
    wait_for_node_tuning_healthy
    oc wait --for=condition=Available numaresourcesscheduler/numaresourcesscheduler --timeout=10m
    for node in $(jq -r '.items[].metadata.name' <<< "${nodes}"); do
        assert_rte_pod_ready_for_mcp worker "${node}" 40 15
        assert_nrt_policy "${node}"
        assert_kubelet_runtime "${node}"
    done
    local final_ds_count
    final_ds_count=$(oc get daemonsets -n openshift-numaresources -o json | jq '[.items[] | select(.metadata.name | startswith("numaresourcesoperator-"))] | length')
    [[ "${final_ds_count}" == "1" ]] || { echo "[FATAL] Expected one NROP worker DaemonSet, found ${final_ds_count}"; return 1; }
    oc get numaresourcesoperator numaresourcesoperator -o json | jq -e '
        (.spec.nodeGroups | length == 1) and
        (.spec.nodeGroups[0].machineConfigPoolSelector.matchLabels == {"pools.operator.machineconfiguration.openshift.io/worker": ""}) and
        (.metadata.annotations["config.numa-operator.openshift.io/pause-reconciliation"] == null)' >/dev/null
    oc get nodes -l 'node-role.kubernetes.io/worker=' -o json | jq -e --arg regular "node-role.kubernetes.io/${NROP_MCP_TARGET}" --arg upgrade "node-role.kubernetes.io/${UPGRADE_MCP_NAME}" '
        all(.items[]; .metadata.labels[$upgrade] == null and ($regular == "node-role.kubernetes.io/worker" or .metadata.labels[$regular] == null))' >/dev/null
    oc get nodes -o json | jq -e '
        ([.items[] | select(.metadata.labels["node-role.kubernetes.io/master"] != null) | .status.nodeInfo.kubeletVersion] | unique) as $masters |
        ($masters | length == 1) and
        all(.items[] | select(.metadata.labels["node-role.kubernetes.io/worker"] != null); .status.nodeInfo.kubeletVersion == $masters[0])' >/dev/null
    [[ -z "$(oc get mcp "${UPGRADE_MCP_NAME}" -o name --ignore-not-found)" ]]
    if [[ "${NROP_MCP_TARGET}" != "worker" ]]; then
        [[ -z "$(oc get mcp "${NROP_MCP_TARGET}" -o name --ignore-not-found)" ]]
    fi
    if [[ -n "${MANAGED_CANARY_PROFILE}" ]]; then
        [[ -z "$(oc get performanceprofile "${regular_profile}" -o name --ignore-not-found)" ]]
        [[ -z "$(oc get performanceprofile "${MANAGED_CANARY_PROFILE}" -o name --ignore-not-found)" ]]
    fi
    echo "[VERIFY] All workers converged on the standard worker pool with healthy NROP and tuning"
}

case "${PHASE}" in
    setup)
        phase_setup
        ;;
    migrate)
        phase_migrate
        ;;
    cleanup)
        phase_cleanup
        ;;
    normalize)
        phase_normalize
        ;;
    *)
        echo "[ERROR] Unknown phase: ${PHASE}. Use: setup, migrate, cleanup, normalize"
        exit 1
        ;;
esac
