# spoke_vm_provisioning

Creates a Telco-KPIs spoke master as a KVM VM on the hypervisor declared by the
spoke's Vault inventory, so the existing ZTP playbooks can install it through
sushy-tools/Redfish.

## Inputs

The role reads the standard `inventories/ocp-deployment` inventory:

- `group_vars/masters`:
  - `vendor: KVM`
  - `hypervisor: <hypervisor-fqdn>`
  - `vm_host: hypervisor`
  - `vm_spec_string` with `cpu_cores`, `ram_mib`, `disk_size_gb`,
    `vm_bridge_interface`, optional `additional_vm_install_options`
  - `bmc_user`, `bmc_password`
- `host_vars/master0`:
  - `hostname`, `uuid`, `mac`
- `host_vars/hypervisor`: SSH access to the selected hypervisor

Only SNO is supported (exactly one master).

## Behaviour

1. Validates the inventory and Vault keys, the bridge, and sushy-tools.
2. Acquires the telco-kpis `vm_bastion_deploy` remote lock on the hypervisor.
3. Leaves an existing domain untouched unless `spoke_vm_provisioning_recreate`
   is true.
4. Creates the qcow2 disk and the libvirt domain via
   `redhatci.ocp.create_vms`, honoring `additional_vm_install_options`.
5. Powers the domain off so sushy/Redfish performs the first boot.
6. Releases the lock immediately (the ZTP deployment runs unlocked).
7. Waits for sushy to expose `/redfish/v1/Systems/<uuid>` and prints the
   `redfish-virtualmedia+...` BMC address.

## Usage

Called only from `playbooks/telco-kpis/deploy-spoke-ztp.yml`:

```yaml
- name: Provision VM-based spoke when defined in Vault
  hosts: hypervisor
  gather_facts: false
  tasks:
    - include_role:
        name: spoke_vm_provisioning
      when:
        - groups['masters'] | default([]) | length > 0
        - hostvars[groups['masters'][0]].vendor | default('') | lower == 'kvm'
```
