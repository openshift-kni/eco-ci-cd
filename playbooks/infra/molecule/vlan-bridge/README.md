# VLAN bridge Molecule test

This scenario boots a **local libvirt VM**, creates a disposable `testuplink`
connected to `br-existing` inside the guest, runs the real
`configure-vlan-bridge.yml` for VLAN 418, checks that `testuplink` remains on
its original bridge, and runs Molecule's idempotence phase (zero changes on
the second converge).

Prerequisites: 
 - `molecule`, 
 - `virt-install`, 
 - `virsh`, 
 - `qemu-img`
 - an active local libvirt `default` network, 
 - `community.general`
 - qcow2 Linux cloud image with NetworkManager, cloud-init, and Python 3. 

The source image must be readable by both the test user and the system libvirt 
QEMU user.

Environment variables:

 - MOLECULE_BRIDGE_IMAGE: the absolute path to the cloud image name to use for 
   the OS on which the test will run, 
   e.g. /home/myuser/tmp/Fedora-Cloud-Base-Generic-42-1.1.x86_64.qcow2

```sh
export MOLECULE_BRIDGE_IMAGE=/path/to/cloud-image.qcow2
cd playbooks/infra
molecule test -s vlan-bridge
```

The test uses a qcow2 overlay, not the source image. Molecule destroys its VM
after the test. If VM creation fails before the instance inventory is written,
inspect the local `molecule-vlan-bridge` VM before removing it manually.
