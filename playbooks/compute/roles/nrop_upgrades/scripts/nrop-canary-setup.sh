#!/bin/bash
# Canary setup: prepare the pool and pause regular workers.

phase_setup() {
    echo "[INFO] === CANARY SETUP PHASE ==="

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
  - machineConfigPoolSelector:
      matchLabels:
        pools.operator.machineconfiguration.openshift.io/${UPGRADE_MCP_NAME}: ""
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
