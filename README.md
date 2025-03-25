# eco-ci-cd

Ansible playbooks for the Telco Verification CI/CD.

## Overview
This repository contains a collection of Ansible playbooks and roles designed to automate various OpenShift (OCP) operations for Telco Verification CI/CD pipelines.

## Available Roles

| Role Name | Purpose | Documentation |
|-----------|---------|---------------|
| oc_client_install | Installs the OpenShift CLI (oc) client | [Documentation](playbooks/roles/oc_client_install/) |
| ocp_operator_deployment | Manages the deployment of operators in OpenShift | [Documentation](playbooks/roles/ocp_operator_deployment/) |
| ocp_version_facts | Manages OpenShift version information and sets various version-related facts | [Documentation](playbooks/roles/ocp_version_facts/) |

## Prerequisites

- Ansible 2.9+

### Installing Project Requirements

```bash
# Clone the repository
git clone https://github.com/yourusername/eco-ci-cd.git
cd eco-ci-cd

# Install Ansible collection dependencies (if any)
ansible-galaxy collection install -r requirements.yml
```

## License
GPL v3.0

