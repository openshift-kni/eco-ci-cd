# kubernetes.core.k8s_exec IPv6 Fallback Issue

**Status:** Root cause identified  
**Severity:** High (breaks pod exec operations)  
**Affected:** Environments with dual-stack DNS but IPv6 routing disabled  
**Workaround:** Use `oc exec` via `ansible.builtin.shell` instead of `kubernetes.core.k8s_exec`  
**Date Identified:** 2026-04-30

---

## Symptoms

When using `kubernetes.core.k8s_exec` to execute commands in pods:

```yaml
- name: Get BIOS version via dmidecode
  kubernetes.core.k8s_exec:
    namespace: openshift-machine-config-operator
    pod: "{{ mcd_pod }}"
    container: machine-config-daemon
    command: chroot /rootfs dmidecode -t 0
    kubeconfig: "{{ spoke_kubeconfig }}"
  register: dmidecode_result
  failed_when: false
```

**Error:**
```
"failed": true,
"msg": "Failed to execute on pod machine-config-daemon-l7lc9 due to : (0)\nReason: [Errno 113] No route to host\n"
```

**Meanwhile, `oc exec` works perfectly:**
```bash
oc --kubeconfig /tmp/spree-02-kubeconfig \
  -n openshift-machine-config-operator \
  exec machine-config-daemon-l7lc9 \
  -c machine-config-daemon \
  -- chroot /rootfs dmidecode -t 0
# Returns BIOS version successfully
```

---

## Root Cause

**TL;DR:** The Python `websocket-client` library (used by `kubernetes.core.k8s_exec`) does not fall back to IPv4 when IPv6 connection fails.

### Detailed Explanation

1. **DNS returns both IPv6 and IPv4 addresses:**
   ```
   api.spree-02.kpi.telcoqe.eng.rdu2.dc.redhat.com
     → 2620:52:9:1698::14 (IPv6)
     → 10.6.152.14 (IPv4)
   ```

2. **IPv6 routing is not configured in this network:**
   ```bash
   $ ping6 2620:52:9:1698::14
   From 2620:52:0:2ebe:172:16:180:1 icmp_seq=1 Destination unreachable: Address unreachable
   
   $ ping 10.6.152.14
   64 bytes from 10.6.152.14: icmp_seq=1 ttl=60 time=0.478 ms  # ✅ Works
   ```

3. **Different fallback behaviors:**

   | Tool | Tries IPv6 | IPv6 Fails | Falls Back to IPv4 | Result |
   |------|------------|------------|-------------------|---------|
   | `curl` | ✅ | ✅ | ✅ | **SUCCESS** |
   | `oc exec` | ✅ | ✅ | ✅ | **SUCCESS** |
   | Python `websocket-client` | ✅ | ✅ | ❌ | **FAILS** |

4. **Code path in Python kubernetes client:**
   ```
   kubernetes.stream.stream()
     → kubernetes.stream.ws_client.websocket_call()
       → websocket.create_connection()
         → socket.connect(('2620:52:9:1698::14', 6443))  # IPv6 only
           → OSError: [Errno 113] No route to host
   ```

   The Python `websocket-client` library (`/home/telcov10n/.local/lib/python3.9/site-packages/websocket/_http.py`) does not implement happy eyeballs (RFC 8305) or IPv4 fallback.

---

## Investigation Timeline

### Initial Hypothesis (WRONG)
Initially suspected WebSocket protocol was blocked while SPDY was allowed:
- ❌ Firewall blocking WebSocket traffic
- ❌ Network policy differences
- ❌ Proxy configuration issues
- ❌ Certificate validation problems

### Breakthrough Tests

**Test 1: curl with WebSocket upgrade**
```bash
curl -k -v \
  --header "Connection: Upgrade" \
  --header "Upgrade: websocket" \
  "https://api.spree-02.kpi.telcoqe.eng.rdu2.dc.redhat.com:6443/..."
  
# Result: HTTP 403 (authentication issue, NOT network block)
# ✅ Proved WebSocket protocol reaches the server!
```

**Test 2: Python websocket library with debug**
```python
# Monkey-patched socket.connect() to see connection attempts
WEBSOCKET TRYING TO CONNECT TO: ('2620:52:9:1698::14', 6443, 0, 0)
# ↑ IPv6 address!

# Result: [Errno 113] No route to host
```

**Test 3: IPv6 vs IPv4 connectivity**
```bash
ping6 2620:52:9:1698::14  # ❌ Destination unreachable
ping 10.6.152.14          # ✅ Success
```

**Conclusion:** IPv6 fallback issue, NOT protocol blocking.

---

## Workaround (Implemented)

Replace `kubernetes.core.k8s_exec` with `ansible.builtin.shell` + `oc exec`:

**Before (BROKEN):**
```yaml
- name: Get BIOS version via dmidecode
  kubernetes.core.k8s_exec:
    namespace: openshift-machine-config-operator
    pod: "{{ mcd_pod }}"
    container: machine-config-daemon
    command: chroot /rootfs dmidecode -t 0
    kubeconfig: "{{ spoke_kubeconfig }}"
  register: dmidecode_result
  failed_when: false
```

**After (WORKING):**
```yaml
- name: Get BIOS version via dmidecode
  ansible.builtin.shell: |
    oc --kubeconfig {{ spoke_kubeconfig }} \
      -n openshift-machine-config-operator \
      exec {{ mcd_pod }} \
      -c machine-config-daemon \
      -- chroot /rootfs dmidecode -t 0
  register: dmidecode_result
  failed_when: false
  changed_when: false
```

**Why this works:** The `oc` binary correctly implements IPv4 fallback when IPv6 fails.

---

## Permanent Solutions (Not Implemented)

### Option 1: Force IPv4 Resolution in kubeconfig
Edit kubeconfig to use IP address instead of hostname:

```yaml
# Before:
server: https://api.spree-02.kpi.telcoqe.eng.rdu2.dc.redhat.com:6443

# After:
server: https://10.6.152.14:6443
```

**Pros:** Python client will use IPv4 directly  
**Cons:** 
- Breaks certificate validation (hostname mismatch)
- Requires manual kubeconfig modification
- Not portable across environments

### Option 2: Configure IPv6 Routing
Enable IPv6 routing on the network infrastructure.

**Pros:** Fixes root cause  
**Cons:** 
- Requires infrastructure changes
- May not be feasible in all environments

### Option 3: Patch Python websocket-client Library
Contribute IPv4 fallback logic to `websocket-client` library.

**Pros:** Benefits all users  
**Cons:** 
- Requires upstream contribution
- Long-term solution
- Would still need workaround until adopted

### Option 4: Disable IPv6 in Python
Set environment variable or Python socket configuration to prefer IPv4.

**Pros:** System-wide fix  
**Cons:**
- Affects all Python applications
- May break IPv6-dependent services
- Fragile workaround

---

## Files Modified

**Commit:** `bb5e97f` - "Fix BIOS/microcode collection: Replace k8s_exec with oc exec"

- `playbooks/telco-kpis/tasks/collect-node-info.yml`
  - Line 59-67: dmidecode (BIOS version)
  - Line 79-87: /proc/cpuinfo (microcode version)
  - Line 99-107: lscpu (CPU model)

All three k8s_exec calls replaced with shell + oc exec.

---

## Verification

**Before fix (build 5, 6):**
```json
{
  "bios_version": "unknown",
  "microcode_version": "unknown",
  "cpu_type": "unknown"
}
```

**After fix (build 7):**
```json
{
  "bios_version": "2.8.2",
  "microcode_version": "0x2b000661",
  "cpu_type": "Intel(R) Xeon(R) Gold 6433N"
}
```

---

## Related Issues

- **OCPBUGS-XXXXX:** (if applicable)
- **Upstream websocket-client:** https://github.com/websocket-client/websocket-client/issues
- **RFC 8305:** "Happy Eyeballs Version 2: Better Connectivity Using Concurrency"

---

## Lessons Learned

1. **"No route to host" doesn't always mean network blocking**
   - Can also indicate IPv6 routing issues
   - Always check both IPv4 and IPv6 connectivity

2. **Not all HTTP clients handle dual-stack DNS equally**
   - curl: Smart (tries both, falls back)
   - oc: Smart (handles fallback)
   - Python websocket-client: Not smart (no fallback)

3. **kubernetes.core modules have hidden dependencies**
   - k8s_exec depends on websocket-client library behavior
   - Library bugs can break Ansible modules
   - Shell + oc exec is more reliable in edge cases

4. **Always test assumptions**
   - Initial hypothesis (WebSocket protocol blocked) was wrong
   - Debug tools revealed the real issue (IPv6)
   - Instrumentation (socket connect debug) was key

---

## Test Script

Reproduce the issue with this script:

```bash
# scripts/quick-test-k8s-exec.sh
ssh telco-kpis-prow-kni-qe-71-bastion "bash -s" < scripts/quick-test-k8s-exec.sh
```

Expected output:
- ✅ oc exec: SUCCESS
- ❌ Python kubernetes client: ERROR (No route to host)
- Shows IPv6 connection attempt details

---

## References

- Investigation thread: (link to Git commits bb5e97f, 1e03b5f)
- Python kubernetes client: https://github.com/kubernetes-client/python
- websocket-client library: https://github.com/websocket-client/websocket-client
- RFC 8305 (Happy Eyeballs): https://tools.ietf.org/html/rfc8305

---

**Conclusion:** The Python `kubernetes` library's dependency on `websocket-client` lacks IPv4 fallback when IPv6 fails. In dual-stack environments without IPv6 routing, use `oc exec` via shell instead of `kubernetes.core.k8s_exec`.
