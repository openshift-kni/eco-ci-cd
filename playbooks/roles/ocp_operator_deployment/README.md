# OCP Operator Deployment Ansible Role

## Disclaimer
This role is provided as-is, without any guarantees of support or maintenance.  
The author or contributors are not responsible for any issues arising from the use of this role. Use it at your own discretion.

## Overview
The `ocp_operator_deployment` Ansible role automates the deployment of OpenShift operators using the **Operator Lifecycle Manager (OLM)**. It supports different catalog sources, including **stage, pre-ga, and brew** repositories.

## Features
- Ensures required variables are defined before execution.
- Deploys operators from different catalog sources (`stage`, `pre-ga`, `brew`).
- Creates **CatalogSource** and required **secrets** dynamically.
- Installs and configures operators using OLM.
- Supports custom **OperatorGroup** configurations.
- Applies default operator configurations if available.

## Requirements
- Ansible **2.9+**
- OpenShift Cluster **4.x**
- redhatci.ocp.catalog_source
- redhatci.ocp.catalog_source
- [`kubernetes.core` collection](https://docs.ansible.com/ansible/latest/collections/kubernetes/core/index.html) installed:
  ```sh
  ansible-galaxy collection install kubernetes.core

## Role Variables

### Required Variables

- **`ocp_operator_deployment_operators`** – List of operators to deploy.
- **`ocp_operator_deployment_version`** – Version of the deployment.

### Optional Variables

- **`ocp_operator_deployment_catalog_source_ns`** (default: `"openshift-marketplace"`)  
  Namespace for the CatalogSource.

- **`ocp_operator_deployment_stage_repo_image`**  
  Image for the stage CatalogSource (**required if using `stage` catalog**).

- **`ocp_operator_deployment_stage_cs_secret`**  
  Secret for accessing the stage registry (**required if using `stage` catalog**).

- **`ocp_operator_deployment_default_label`** (default: `{}`)  
  Default labels for operator namespaces.

## Operator List Example

Each operator should be defined with the required parameters:

```yaml
ocp_operator_deployment_operators:
  - name: "example-operator"
    namespace: "example-namespace"
    catalog: "stage"
    channel: "stable" # optional
    og_spec: # optional
      targetNamespaces:
        - "example-namespace"
    starting_csv: "example-operator.v1.2.3" # optional

## Usage

### Basic Playbook Example - deploy from prod

```yaml
- name: Deploy OpenShift Operators
  hosts: localhost
  roles:
    - role: ocp_operator_deployment
      vars:
        ocp_operator_deployment_version: "4.16"
        ocp_operator_deployment_operators:
          - name: "example-operator"
            namespace: "example-namespace"
            catalog: "stage"
            channel: "stable"
```

## Tasks Breakdown

1. **Verify Required Variables**  
   - Ensures all required inputs are provided before execution.

2. **Deploy CatalogSources**  
   - Creates the necessary **CatalogSource** in OpenShift.  
   - Generates required **secrets** for the registry.

3. **Deploy Operators**  
   - Uses **OLM** to deploy specified operators.  
   - Supports different installation **channels**.

4. **Apply Configurations**  
   - Automatically applies **default operator configurations** (if available).

## Dependencies

This role does not have any hard dependencies but requires the [`kubernetes.core`](https://docs.ansible.com/ansible/latest/collections/kubernetes/core/index.html) collection.

## License

Apache

## Authors

- **Nikita Kononov**

## Contributions

Feel free to **open issues** or **submit PRs** to enhance functionality!
