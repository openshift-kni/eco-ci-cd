# Ansible Role: `kickstart_iso`

## Disclaimer
This role is provided as-is, without any guarantees of support or maintenance.  
The author or contributors are not responsible for any issues arising from the use of this role. Use it at your own discretion.

## Description
This Ansible role automates the creation of a bootable ISO image customized with a Kickstart file for automated installations. It performs the following tasks:
- Downloads an ISO file.
- Mounts the ISO and extracts its contents.
- Configures a Kickstart file for automated installation.
- Updates bootloader configurations to include the Kickstart installation option.
- Creates a new bootable ISO with the updated configurations.

## Requirements
- Ansible 2.9 or newer.
- Required packages installed on the control node:
  - `rsync`
  - `mkisofs`
  - `sshpass`
- The target system must support ISO mounting and the necessary filesystem tools.


## Role Variables
The following variables can be configured please notice some of the variables are **required**:

| Variable Name                       | Default Value      | Description|
|-------------------------------------|--------------------|------------|
|`kickstart_iso_file_desire_location` |                     | Target directory where the generated ISO file will be moved after creation. **Required**. Example: `/opt/http_store/data`|
|`kickstart_iso_timezone`             |                     | Timezone to set in the Kickstart configuration file. **Required**. Example: `America/Toronto`                            |
|`kickstart_iso_password`             |                     | Root password to set in the Kickstart configuration file. **Required**.                                                  |
|`kickstart_iso_username`             |                     | Username to create in the Kickstart configuration file. **Required**.                                                    |
|`kickstart_iso_net_config`           |                     | Network configuration for the target system in the Kickstart file. **Required**.   See example below                     |
|`kickstart_iso_dest_dir`             | `/tmp`              | Directory to store the downloaded ISO and generated files.                                                               |
|`kickstart_iso_mount_path`           | `/tmp/mount`        | Directory where the ISO will be mounted.                                                                                 |
|`kickstart_iso_os_install_path`      | `/tmp/os-install`   | Working directory for extracted ISO contents.                                                                            |
|`kickstart_iso_name`                 | `installation.iso`  | Name of the final bootable ISO.                                                                                          |
|`kickstart_iso_link`                 | `https://download.fedoraproject.org/pub/fedora/linux/`<br>`releases/41/Workstation/x86_64/iso/`<br>`Fedora-Workstation-Live-x86_64-41-1.4.iso` | URL of the ISO image to download. |

```yaml
kickstart_iso_net_config:
  interface_name: "eth0"
  hostname: "myserver.local"
  ip: "192.168.1.10"
  mask: "255.255.255.0"
  gw: "192.168.1.1"
  dns: "8.8.8.8"
```
## Handlers
The role includes handlers to clean up temporary files and directories:
- Remove mount directory.
- Remove working directory.
- Remove installation ISO after use.

## Dependencies
This role does not depend on other roles but requires certain utilities to be installed on the target system.



## Example Playbook
Here’s an example of how to use this role in your playbook:

```yaml
---
- name: Create a Kickstart-enabled ISO
  hosts: localhost
  become: true
  roles:
    - role: kickstart_iso
      vars:
        kickstart_iso_name: "custom-fedora.iso"
        kickstart_iso_link: "https://download.fedoraproject.org/pub/fedora/linux/releases/41/Workstation/x86_64/iso/Fedora-Workstation-Live-x86_64-41-1.4.iso"
        kickstart_iso_file_desire_location: "/home/user/iso"
        kickstart_iso_timezone: "America/Toronto"
        kickstart_iso_password: "your_password"
        kickstart_iso_username: "your_user"
        kickstart_iso_net_config:
          interface_name: "eth0"
          hostname: "myserver.local"
          ip: "192.168.1.10"
          mask: "255.255.255.0"
          gw: "192.168.1.1"
          dns: "8.8.8.8"
```
License
-------

Apache

