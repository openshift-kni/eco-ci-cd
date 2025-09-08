# openshift-kni rules

This rule checks for compliance with some coding conventions in the OCP
collection

The `openshift-kni` rule has the following checks:

- `openshift-kni[no-role-prefix]` - Variables used within a role should have a
  prefix related to the role. This includes:
  1. Variables passed to `{include,import}_role` and `{include_import}_tasks`
     should be named `$prefix_$var`
  1. Facts saved from within roles should be named `$prefix_$fact`
  1. Variables registered from tasks to use in subsequent tasks should be named
     `_$prefix_$var` - notice the extra underscore to signal this variable is
     "private"

  The rules to figure out the prefix are:
  1. If the role name is $SHORT (where $SHORT is < 6 characters) use the whole
     name
  1. If not, split the role name by underscores into words
  1. If there's a single word:
     - Check for digits pattern `<prefix><digits><suffix>` (e.g., `junit2json`)
       and create acronym using first letter of prefix + digits + first letter
       of suffix
     - Otherwise, use the first $SHORT characters
  1. Finally, if there are 2 or more words, build an acronym from the split
     words
  1. It is also possible to specify the full prefix of the role (doesn't matter
     if it's "too long") or prefix it with `global_` if the variable is
     intended for global scope.

  Examples of valid prefixes:

  | Role Name               | Computed Prefix | Full Prefix              | Global Prefix |
  |-------------------------|-----------------|--------------------------|---------------|
  | `sno`                   | `sno_`          | `sno_`                   | `global_`     |
  | `installer`             | `instal_`       | `installer_`             | `global_`     |
  | `junit2json`            | `j2j_`          | `junit2json_`            | `global_`     |
  | `web3server`            | `w3s_`          | `web3server_`            | `global_`     |
  | `validate_http_store`   | `vhs_`          | `validate_http_store_`   | `global_`     |
  | `oc_client_install`     | `oci_`          | `oc_client_install_`     | `global_`     |

!!! note

This rule overlaps with the `var-naming[no-role-prefix]` stock rule, disable
it in your `.ansible-lint` config file or by passing a -x flag

## Problematic Code

```yaml
---
- name: Example playbook with bad variable naming
  hosts: all
  tasks:
    - name: Include the OC Client Install role
      ansible.builtin.include_role:
        name: oc_client_install
        vars:
          version: "4.15.0"  # <-- Bad: no prefix
          install_dir: "/usr/local/bin"  # <-- Bad: no prefix
    
    - name: Include role with digits in name
      ansible.builtin.include_role:
        name: junit2json
        vars:
          config_file: "config.xml"  # <-- Bad: no prefix
    
    - name: Set facts without prefix
      ansible.builtin.set_fact:
        ocp_version: "4.15.0"  # <-- Bad: no prefix for role context
    
    - name: Command with bad register
      ansible.builtin.command: echo "test"
      register: result  # <-- Bad: private var without prefix
...
```

## Correct Code

```yaml
---
- name: Example playbook with correct variable naming
  hosts: all
  tasks:
    - name: Include the OC Client Install role
      ansible.builtin.include_role:
        name: oc_client_install
        vars:
          oci_version: "4.15.0"  # <-- Good: computed prefix
          oc_client_install_install_dir: "/usr/local/bin"  # <-- Good: full prefix
          global_cleanup: true  # <-- Good: global variable
    
    - name: Include role with digits in name
      ansible.builtin.include_role:
        name: junit2json
        vars:
          j2j_config_file: "config.xml"  # <-- Good: computed prefix with digits
          junit2json_output_dir: "/tmp"  # <-- Good: full prefix
    
    - name: Set facts with proper prefix
      ansible.builtin.set_fact:
        oci_ocp_version: "4.15.0"  # <-- Good: role context prefix
        global_cluster_info: "some_value"  # <-- Good: global scope
    
    - name: Command with good register
      ansible.builtin.command: echo "test"
      register: _oci_command_result  # <-- Good: private var with prefix
...
```

## Private Variables for Registered Tasks

Variables registered from tasks should use a leading underscore to indicate they are private to the role:

```yaml
- name: Get cluster version
  ansible.builtin.command: oc version
  register: _oci_version_output  # <-- Good: private with computed prefix

- name: Check installation status  
  ansible.builtin.stat:
    path: /usr/local/bin/oc
  register: _oc_client_install_binary_stat  # <-- Good: private with full prefix
```
