# configurecluster

This Ansible role is responsible for configuring NTO (Node Tuning Operator) clusters.

## Description

- Creates Machine Config pool
- Generates performance profile from `performance-profile-creator`
- Save a copy to `artifacts_folder`
- apply's all manifests 

### Dependencies

This role depends on the `kubernetes.core` collection, and it uses Python packages like `kubernetes` and `PyYAML`.

### Variables

- **artifacts_folder**: The directory where artifacts are stored.
- **ignore_cgroups_version**: A flag to ignore the cgroup version.
- **rt_kernel**: A flag to indicate if real-time kernel should be enabled.


| Variable                  | Description | Default Value
|---|---|---|
| artifacts_folder          | Saves logs files      | /artifacts 
| ignore_cgroups_version    | Ignore Cgroup version | true
| rt_kernel                 | Enable RT kernel      | false
| hugepages                 | Dict Contains hugepages config | ""


#### Hugepages config example
```yaml
hugepages
    size: <defaultHugepagesSize>
    pages:
        - count: 1
          size: 1G
        - count: 128
          size: 2M
```

### Examples

Here is an example of how to use this role in a playbook:

```yaml
- name: Deploy NTO configuration
  hosts: bastion
  gather_facts: false
  environment:
    K8S_AUTH_KUBECONFIG: "{{ kubeconfig }}"
  vars:
    kubeconfig: "<kubeconfig path>"  

  roles:
    - role: configurecluster
    
```

Make sure to have the necessary variables like `kubeconfig` defined, as well as the required dependencies installed.