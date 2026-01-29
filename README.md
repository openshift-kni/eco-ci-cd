# eco-ci-cd



Comprehensive Ansible automation framework for Telco Verification CI/CD pipelines, providing end-to-end OpenShift cluster deployment, CNF testing, and infrastructure management capabilities.

## Overview

This repository contains a comprehensive collection of Ansible playbooks, roles, and automation tools designed to streamline Telco Verification CI/CD operations. The framework supports:

- **OpenShift Cluster Deployment**: Automated hybrid multinode OCP deployment with agent-based installation
- **Infrastructure Management**: Bare-metal hypervisor and VM bastion deployment automation
- **CNF Testing**: Cloud-Native Network Function testing and validation frameworks
- **Operator Management**: Automated OpenShift operator deployment and configuration

## Available Roles

### Core Infrastructure Roles

| Role Name | Purpose | Documentation |
|-----------|---------|---------------|
| `oc_client_install` | Installs and configures OpenShift CLI (oc) client | [Documentation](playbooks/roles/oc_client_install/) |
| `ocp_operator_deployment` | Manages OpenShift operator lifecycle and deployment | [Documentation](playbooks/roles/ocp_operator_deployment/) |
| `ocp_version_facts` | Retrieves and manages OpenShift version information | [Documentation](playbooks/roles/ocp_version_facts/) |

### Infrastructure Deployment Roles

| Role Name | Purpose | Documentation |
|-----------|---------|---------------|
| `kickstart_iso` | Creates custom kickstart ISO images for bare-metal deployment | [Documentation](playbooks/infra/roles/kickstart_iso/) |
| `registry_gui_deploy` | Deploys container registry with GUI interface | [Documentation](playbooks/infra/roles/registry_gui_deploy/) |

### Compute and Performance Roles

| Role Name | Purpose | Documentation |
|-----------|---------|---------------|
| `configurecluster` | Configures cluster-wide performance and compute settings | [Documentation](playbooks/compute/nto/roles/configurecluster/) |

## Utility Scripts

| Script | Purpose | Usage |
|--------|---------|--------|
| `clone-z-stream-issue.py` | Clone and manage z-stream issues | Issue management automation |
| `fail_if_any_test_failed.py` | Test result validation and failure reporting | CI/CD pipeline validation |
| `send-slack-notification-bot.py` | Send notifications to Slack channels | CI/CD notification system |

## Prerequisites

- **Ansible**: Version 2.9 or higher
- **Python**: Version 3.8 or higher
- **python3-passlib**: Version 1.7.4 or higher
- **SSH Access**: To hypervisor and bastion hosts


## Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/eco-ci-cd.git
cd eco-ci-cd
```

### 2. Install Dependencies

```bash
# Install Ansible collection dependencies
ansible-galaxy collection install -r requirements.yml
```

## License

This project is licensed under the GPL v3.0 License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This automation framework is provided "as-is" and comes with no guarantees. Ensure thorough testing in your environment before deploying to production systems.

