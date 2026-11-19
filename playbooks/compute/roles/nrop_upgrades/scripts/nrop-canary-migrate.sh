#!/bin/bash
# Canary migration: move and verify selected workers.

phase_migrate() {
    echo "[INFO] === CANARY MIGRATE WORKERS PHASE ==="

    log_nrop_status "migrate-start"

    if [[ "${OCP_FROM_MAJOR}" -eq 4 && "${OCP_FROM_MINOR}" -lt 18 ]]; then
        echo "[INFO] Step 9: Adding custom SELinux annotation to worker nodeGroup (upgrading from ${OCP_FROM_MAJOR}.${OCP_FROM_MINOR}, pre-4.18)"
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
  - machineConfigPoolSelector:
      matchLabels:
        pools.operator.machineconfiguration.openshift.io/${UPGRADE_MCP_NAME}: ""
EOF
        oc apply -f "${ARTIFACTS_DIR}/nrop-cr-migrate.yaml"
        assert_nrop_selinux_annotation
    else
        echo "[INFO] Step 9: Skipping SELinux annotation (source ${OCP_FROM_MAJOR}.${OCP_FROM_MINOR} and target share the same built-in SELinux policy)"
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
            assert_rte_pod_running_on_node "${node}" "${UPGRADE_MCP_NAME}"
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
        assert_rte_pod_running_on_node "${node}" "${UPGRADE_MCP_NAME}"
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
            assert_rte_pod_running_on_node "${other_node}" "${NROP_MCP_TARGET}" 5 10
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
