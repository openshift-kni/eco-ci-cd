# Contributing to eco-ci-cd

Thank you for your interest in contributing to the eco-ci-cd project! This document provides guidelines and instructions for contributing to this repository.

## Code of Conduct

Please be respectful and considerate of others when contributing to this project. We aim to foster an inclusive and welcoming community.

## Getting Started

1. Fork the repository
2. Clone your forked repository locally
3. Set up the development environment
4. Create a new branch for your changes

## Development Environment Setup

1. Ensure you have Ansible 2.9+ installed
2. Install required dependencies using the requirements.yaml file:
   ```bash
   ansible-galaxy install -r requirements.yaml
   ```

   Example requirements.yaml:
   ```yaml
   ---
   collections:
     - name: kubernetes.core
     - name: redhatci.ocp
   ```

## Project Structure

The project is organized as follows:

```
eco-ci-cd/
├── playbooks/
│   ├── roles/           # Main roles
│   │   ├── oc_client_install/
│   │   ├── ocp_operator_deployment/
│   │   └── ocp_version_facts/
│   └── infra/           # Infrastructure-related roles
│       └── roles/
│           └── kickstart_iso/
```

## Creating a New Role

When creating a new role, please follow this structure:

```
new_role/
├── defaults/       # Default variables
│   └── main.yml
├── meta/           # Role metadata
│   └── main.yml
├── tasks/          # Task definitions
│   └── main.yml
├── templates/      # Jinja2 templates (if needed)
└── README.md       # Role documentation
```

## Documentation Guidelines

All roles should include a well-documented README.md file with:

1. **Overview**: A brief description of the role's purpose
2. **Disclaimer**: Standard disclaimer about the "as-is" nature of the role
3. **Requirements**: Software, permissions, etc. needed to use the role
4. **Variables**: All variables used by the role, with descriptions
5. **Example Usage**: One or more examples showing how to use the role
6. **Tasks Description**: Explanation of the main tasks performed
7. **Dependencies**: Any dependencies the role has
8. **License**: License information

## Testing

Before submitting a pull request:

1. Test your changes on at least one OpenShift environment
2. Ensure all variables are properly documented
3. Verify that your role follows the project's structure guidelines

## Submitting Changes

1. Create a descriptive commit message
2. Push your changes to your fork
3. Submit a pull request to the main repository
4. Respond to any feedback during the review process

## Style Guidelines

1. Follow Ansible best practices and YAML syntax
2. Use descriptive variable names with appropriate prefixes
3. Include comments for complex tasks
4. Keep tasks focused and modular

## Additional Resources

- [Ansible Best Practices](https://docs.ansible.com/ansible/latest/user_guide/playbooks_best_practices.html)
- [Ansible Role Development Guide](https://docs.ansible.com/ansible/latest/user_guide/playbooks_reuse_roles.html)

Thank you for contributing to eco-ci-cd!

