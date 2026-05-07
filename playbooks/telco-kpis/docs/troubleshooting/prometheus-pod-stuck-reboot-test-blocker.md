# Prometheus Pod Stuck - Reboot Test Blocker

**Last Updated:** 2026-04-29  
**Affected Clusters:** spree-02 (confirmed), potentially all SNO deployments with ACM observability  
**Related Bugs:** OCPBUGS-65953, OCPBUGS-70352  
**Impact:** Reboot tests always skipped due to failed BeforeEach health checks

---

## Problem Description

The `prometheus-k8s-0` pod in the `openshift-monitoring` namespace gets stuck in `Init:0/1` state indefinitely after cluster deployment, preventing the reboot test health checks from passing.

## Symptoms

### 1. Reboot Test Behavior
```bash
# All reboot tests skip execution
Ran 0 of 3 Specs
3 Skipped

# Health check fails with:
Some pods are unhealthy before reboot
```

### 2. Pod Status
```bash
$ oc get pods -n openshift-monitoring | grep prometheus-k8s
prometheus-k8s-0   0/6   Init:0/1   0   12d
```

### 3. Pod Error Logs
```bash
$ oc logs prometheus-k8s-0 -n openshift-monitoring -c init-config-reloader
Error: secret "observability-alertmanager-accessor" not found
```

### 4. Node Uptime
```bash
$ ssh core@<spoke> uptime
12 days, 20:02  # Confirms spoke never rebooted
```

## Root Cause

**Two-Part Issue:**

### Part 1: Mangled ConfigMap YAML (OCPBUGS-65953)
The `alertmanager-main-generated` ConfigMap contains malformed YAML with improper indentation of the `receivers` block:

```yaml
# WRONG (causes parsing failures)
route:
  receiver: Default
receivers:
- name: Default
```

Should be:

```yaml
# CORRECT
route:
  receiver: Default
  receivers:
  - name: Default
```

### Part 2: Missing ACM Observability Secret (OCPBUGS-70352)
The Prometheus CR references `observability-alertmanager-accessor` secret in `spec.additionalAlertManagerConfigs`, but the secret doesn't exist (ACM observability not configured).

**Why This Blocks Reboot Tests:**
- CNF-gotests framework has BeforeEach health check: verifies all pods are Running
- Prometheus pod stuck → health check fails → all tests SKIP
- Spoke never reboots because tests never actually execute

## Workaround / Fix

### Option 1: Two-Step Fix (Recommended)

**Step 1: Fix ConfigMap YAML**

Create temporary YAML file on bastion:

```bash
cat <<'EOF' > /tmp/alertmanager-config-fix.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: alertmanager-main-generated
  namespace: openshift-monitoring
data:
  alertmanager.yaml.gz: H4sIAAAAAAAA/0yOQQrCMBBF95wiSxeVQhcu3HoCwY1gF0k6bQOdSTOTUsRzdmgXrt7j///x5gkf4C8LDmYSaIBzWSnpoGjYo3xVdWAXQmWXCNnSPBg0SBxhzm0p2xrPo1qQVvd+hN9uRs4x8S+VQW9kF+LrO3U51OBaT02BVTwBUZs+8lAyxV3k88SYOr72yC1bX1G6t7neMu08nVmz/QMAAP//jkUArgAAAA==
EOF

oc --kubeconfig /tmp/<spoke>-kubeconfig apply -f /tmp/alertmanager-config-fix.yaml
```

**Step 2: Delete Stuck Pod**

```bash
oc --kubeconfig /tmp/<spoke>-kubeconfig delete pod prometheus-k8s-0 -n openshift-monitoring
```

**Verification:**

```bash
# Wait 1-2 minutes, then check:
oc --kubeconfig /tmp/<spoke>-kubeconfig get pods -n openshift-monitoring | grep prometheus-k8s

# Expected output:
# prometheus-k8s-0   6/6   Running   0   2m
```

### Option 2: Patch Prometheus CR (If additionalAlertManagerConfigs exists)

```bash
# Check if the field exists
oc --kubeconfig /tmp/<spoke>-kubeconfig get prometheus k8s -n openshift-monitoring -o jsonpath='{.spec.additionalAlertManagerConfigs}'

# If output is not empty, remove it:
oc --kubeconfig /tmp/<spoke>-kubeconfig patch prometheus k8s -n openshift-monitoring \
  --type=json -p='[{"op": "remove", "path": "/spec/additionalAlertManagerConfigs"}]'

# Then delete pod
oc --kubeconfig /tmp/<spoke>-kubeconfig delete pod prometheus-k8s-0 -n openshift-monitoring
```

**Note:** In spree-02 testing (2026-04-29), the field didn't exist, so only Step 1 + Step 2 were needed.

## Verification Steps

### 1. Prometheus Pod Health
```bash
# All 6 containers should be Running
oc --kubeconfig /tmp/<spoke>-kubeconfig get pod prometheus-k8s-0 -n openshift-monitoring

# Check logs for errors (should see normal startup)
oc --kubeconfig /tmp/<spoke>-kubeconfig logs prometheus-k8s-0 -n openshift-monitoring -c prometheus --tail=20
```

### 2. Monitor Stability
```bash
# Wait 5 minutes and verify pod stays healthy
watch -n 10 'oc --kubeconfig /tmp/<spoke>-kubeconfig get pods -n openshift-monitoring | grep prometheus-k8s'
```

### 3. Reboot Test Execution
```bash
# Trigger Jenkins job: telco-kpis-run-reboot-test
# Expected output:
# ✅ Health check passes: "All pods are healthy before reboot"
# ✅ Test executes: "Rebooting spoke cluster via oc..."
# ✅ Artifacts show: "Ran 3 of 3 Specs" (not skipped)

# Verify spoke actually rebooted:
ssh core@<spoke> uptime
# Uptime should be < test duration
```

## Prevention for Future Deployments

### Automated Fix in Deployment Playbook

Add post-deployment task to `deploy-ocp-hybrid-multinode.yml` or create dedicated playbook:

```yaml
---
# playbooks/telco-kpis/tasks/fix-prometheus-pod.yml

- name: Fix prometheus pod if stuck (OCPBUGS-65953, OCPBUGS-70352)
  hosts: bastion
  gather_facts: false
  tasks:
    - name: Check if prometheus pod is stuck in Init state
      ansible.builtin.shell: |
        oc --kubeconfig {{ spoke_kubeconfig }} get pod prometheus-k8s-0 -n openshift-monitoring \
          -o jsonpath='{.status.containerStatuses[0].ready}' 2>/dev/null || echo "false"
      register: prometheus_ready
      failed_when: false
      changed_when: false

    - name: Apply prometheus fix if pod is not ready
      when: prometheus_ready.stdout == "false"
      block:
        - name: Create temporary ConfigMap fix file
          ansible.builtin.copy:
            content: |
              apiVersion: v1
              kind: ConfigMap
              metadata:
                name: alertmanager-main-generated
                namespace: openshift-monitoring
              data:
                alertmanager.yaml.gz: H4sIAAAAAAAA/0yOQQrCMBBF95wiSxeVQhcu3HoCwY1gF0k6bQOdSTOTUsRzdmgXrt7j///x5gkf4C8LDmYSaIBzWSnpoGjYo3xVdWAXQmWXCNnSPBg0SBxhzm0p2xrPo1qQVvd+hN9uRs4x8S+VQW9kF+LrO3U51OBaT02BVTwBUZs+8lAyxV3k88SYOr72yC1bX1G6t7neMu08nVmz/QMAAP//jkUArgAAAA==
            dest: /tmp/alertmanager-config-fix.yaml
            mode: '0644'

        - name: Apply ConfigMap fix
          ansible.builtin.command:
            cmd: oc --kubeconfig {{ spoke_kubeconfig }} apply -f /tmp/alertmanager-config-fix.yaml
          changed_when: true

        - name: Delete stuck prometheus pod
          ansible.builtin.command:
            cmd: oc --kubeconfig {{ spoke_kubeconfig }} delete pod prometheus-k8s-0 -n openshift-monitoring
          changed_when: true

        - name: Wait for prometheus pod to become ready (max 5 minutes)
          ansible.builtin.shell: |
            oc --kubeconfig {{ spoke_kubeconfig }} wait --for=condition=Ready \
              pod/prometheus-k8s-0 -n openshift-monitoring --timeout=300s
          register: wait_result
          failed_when: false

        - name: Display prometheus pod status
          ansible.builtin.command:
            cmd: oc --kubeconfig {{ spoke_kubeconfig }} get pod prometheus-k8s-0 -n openshift-monitoring
          changed_when: false

        - name: Cleanup temporary file
          ansible.builtin.file:
            path: /tmp/alertmanager-config-fix.yaml
            state: absent
```

### Integration Points

**Option A: Add to deployment playbook**
```yaml
# In deploy-ocp-hybrid-multinode.yml, after cluster deployment completes:
- name: Post-deployment fixes
  ansible.builtin.include_tasks: telco-kpis/tasks/fix-prometheus-pod.yml
```

**Option B: Add to cluster environment setup**
```yaml
# In setup-cluster-env.yml, before running tests:
- name: Ensure prometheus pod is healthy
  ansible.builtin.include_tasks: telco-kpis/tasks/fix-prometheus-pod.yml
```

**Option C: Standalone playbook**
```yaml
# playbooks/telco-kpis/fix-prometheus-pod.yml
---
- name: Fix stuck prometheus pod (OCPBUGS-65953, OCPBUGS-70352)
  hosts: bastion
  gather_facts: false
  tasks:
    - name: Execute prometheus fix tasks
      ansible.builtin.include_tasks: tasks/fix-prometheus-pod.yml
```

## Related Bugs and References

### OpenShift Bugs
- **OCPBUGS-65953**: Prometheus pod stuck due to mangled ConfigMap YAML
  - Component: Cluster Monitoring Operator
  - Status: Confirmed
  - Workaround: Fix ConfigMap indentation and restart pod

- **OCPBUGS-70352**: Missing ACM observability secret causes init failure
  - Component: Advanced Cluster Management
  - Status: Confirmed
  - Workaround: Remove additionalAlertManagerConfigs reference or install ACM observability

### Documentation
- Prometheus Operator: https://prometheus-operator.dev/
- OpenShift Monitoring: https://docs.openshift.com/container-platform/latest/monitoring/monitoring-overview.html
- CNF-gotests health checks: Uses BeforeEach to verify cluster state before reboot

### Git Commits (Timezone Fix)
- `48e7606` (2026-04-28): Critical timezone fix for test filtering (related issue)
- `b4ea8d0`: Initial timestamp filtering implementation

## Timeline of Issue (spree-02 Example)

**2026-04-17**: Cluster deployed, prometheus pod stuck immediately  
**2026-04-28**: Reboot tests run, all skip (health check fails for 12 days)  
**2026-04-29**: Issue identified and fixed (prometheus pod now healthy)

**Duration of Outage:** 12+ days (from deployment until manual fix applied)

## Lessons Learned

1. **Health checks are critical** - CNF-gotests framework correctly prevented destructive operations (reboot) when cluster monitoring was unhealthy
2. **Post-deployment validation needed** - Should verify all monitoring components are healthy before declaring deployment complete
3. **ACM observability optional** - If not using ACM, Prometheus CR should not reference ACM secrets
4. **ConfigMap validation** - Cluster Monitoring Operator should validate ConfigMap YAML structure before applying

## Action Items

- [ ] Add automated prometheus health check to deployment playbooks
- [ ] Create post-deployment validation playbook for all monitoring components
- [ ] Document ACM observability requirements for production clusters
- [ ] Update cluster deployment checklist with monitoring verification steps
- [ ] Consider adding prometheus fix to `setup-cluster-env.yml` for all CI/CD pipelines

---

**Maintainer:** Telco Verification Team  
**Last Verified:** 2026-04-29 (spree-02 cluster, OCP 4.18)
