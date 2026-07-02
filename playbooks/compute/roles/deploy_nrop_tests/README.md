# nrop_testing Ansible Role

This Ansible role, `nrop_testing`, is designed to automate end-to-end (E2E) testing of the NUMAResource Operator (NRO) inside OpenShift clusters. It is typically run from the bastion host and launches a containerized test suite using parameters defined by playbook or inventory variables.

## What Does This Role Do?

- Launches E2E NRO/NUMA tests using the official test image and cluster `kubeconfig`
- Supports both connected and disconnected OpenShift environments (mirrored images, etc)
- Allows fine-grained control over test selection, timeouts, device types, and teardown/cooldown parameters
- Collects junit test results for reporting in downstream CI pipelines

## Expected Variables

You can adjust the execution by providing the following variables:

| Variable               | Required | Description                                                        |
|------------------------|----------|--------------------------------------------------------------------|
| `kubeconfig`           | Yes      | Path to kubeconfig for OpenShift cluster under test                 |
| `nrop_test_image_tag`  | No       | Full image reference (pullspec) for the E2E test container          |
| `numa_mustgather_image`| No       | Image for must-gather (debug)                                      |
| `disconnected_install` | No       | Set `true` for disconnected installs (default: `true`)              |
| `teardown_timeout`     | No       | Timeout override for teardown stage                                 |
| `cooldown_timeout`     | No       | Timeout override for cooldown stage                                 |
| `sample_device_type_1/2/3` | No   | Custom device type override variables                               |
| `ginkgo_focus`         | No       | Regex/filter to focus a subset of E2E tests                        |
| `ginkgo_skip`          | No       | Regex/filter to skip a subset of E2E tests                         |
| `run_reboot_tests_only`| No       | Run only tests that require node reboots (`true/false`)             |
| `ginkgo_label`         | No       | Custom test label filter                                            |
| `skip_filter`          | No       | Additional skip filter for label selection                          |

Variables should be declared where you invoke the role, usually as `vars:` in your playbook or via inventory/group_vars/host_vars.

## Example Usage

```yaml
- name: Run NRO/NROP E2E Tests
  hosts: bastion
  roles:
    - role: nrop_testing
      vars:
        nrop_test_dir: "/tmp/nrop-junit"
        kubeconfig: "/home/runner/.kube/config"
        nrop_test_image_tag: "quay.io/openshift-kni/numaresources-operator-tests:4.17"
        numa_mustgather_image: "quay.io/openshift-kni/numaresources-must-gather"
        disconnected_install: true
        teardown_timeout: "600"           # optional, in seconds
        cooldown_timeout: "60"            # optional, in seconds
        ginkgo_focus: ""                  # optional
        ginkgo_skip: "Flaky"              # optional
        run_reboot_tests_only: false      # optional
```

## What Gets Executed?

The main template, [templates/nrop_test_script.j2](templates/nrop_test_script.j2), renders a Podman command that runs the E2E test image, mounts your KUBECONFIG and artifact directories, and passes environment variables to control test selection and execution. This produces `junit.xml` reports in your specified results directory.

Sample rendered command snippet:
```
podman run --rm --name nrop-container-tests \
  --entrypoint /usr/local/bin/run-e2e-nrop-serial.sh \
  --net=host \
  -v /tmp/nrop-junit:/nrop:z \
  -v /home/runner/.kube/config:/tmp/kubeconfig:z \
  -e KUBECONFIG=/tmp/kubeconfig \
  ...
  quay.io/openshift-kni/numaresources-operator-tests:4.17 \
    --report-file /nrop/junit/junit.xml \
    --focus "mytest" \
    --label-filter "!reboot_required"
```

## Recommendations

- Ensure your bastion host can run Podman containers and has necessary SELinux permissions
- The `kubeconfig` should have sufficient privileges to install/uninstall operators and create resources

## Output

- The role will create or update the directory indicated by `nrop_test_dir` with:
  - Test logs
  - JUnit XML reports (`junit.xml`)
- These can be used for reporting, CI/CD status checks, and debugging failures