# Ansible Role: deploy_registry

## Disclaimer
This role is provided as-is, without any guarantees of support or maintenance.  
The author or contributors are not responsible for any issues arising from the use of this role. Use it at your own discretion.

## Description
This Ansible role sets up a local container image registry with a web UI and an Nginx load balancer using Podman containers. It also integrates TLS, authentication, and optional registry mirroring support.

## 🧩 Features

- Deploys a secure internal registry with TLS and htpasswd auth  
- Runs a web-based registry UI (e.g., [joxit/docker-registry-ui](https://github.com/Joxit/docker-registry-ui))  
- Provides an Nginx-based reverse proxy/load balancer  
- Configures systemd services for container supervision  
- Opens required firewall ports  
---

## ⚙️ Role Variables

The following variables must be defined by the user:

### 🔐 TLS & Authentication

| Variable | Description |
|---------|-------------|
| `registry_gui_tls_cert` | TLS certificate (string content) |
| `registry_gui_tls_cert_key` | TLS private key (string content) |
| `registry_gui_htpasswd_content` | Htpasswd file content for basic auth |
| `registry_gui_pull_secret` | JSON-formatted pull secret content |
| `registry_gui_secret` | Internal registry secret |

### 📦 Registry Configuration

| Variable | Description |
|----------|-------------|
| `registry_gui_name` | Container name for the registry |
| `registry_gui_port` | Port number for the registry (default: `5000`) |
| `registry_gui_web_port` | NGINX frontend port (default: `80`) |
| `registry_gui_user` | Registry username |
| `registry_gui_pass` | Registry password |
| `registry_gui_registry_image` | Image for the registry container (e.g., `registry:2`) |
| `registry_gui_registry_ui_image` | Image for the UI container |
| `registry_gui_registry_ui_container_name` | Name of the UI container |
| `registry_gui_nginx_lb_container_name` | Name of the Nginx container |
| `registry_gui_local_pull_secret_path` | Path where pull secret will be stored |
| `registry_gui_cert_dir` | Directory for cert/key files |
| `registry_gui_nginx_config_dir` | Directory for nginx.conf |
| `registry_gui_nginx_lb_image` | Image for the nginx container (e.g., `nginx:1.24-alpine`) |

---

## 🔧 Example Playbook

```yaml
- name: Deploy internal container registry
  hosts: bastion
  become: true
  roles:
    - role: registry_gui_deploy
      vars:
        registry_gui_name: "registry.local"
        registry_gui_port: 5000
        registry_gui_user: "admin"
        registry_gui_pass: "password"
        registry_gui_tls_cert: "{{ lookup('file', 'files/registry.crt') }}"
        registry_gui_tls_cert_key: "{{ lookup('file', 'files/registry.key') }}"
        registry_gui_htpasswd_content: "{{ lookup('file', 'files/htpasswd') }}"
        registry_gui_pull_secret: "{{ lookup('file', 'files/pull-secret.json') }}"
        registry_gui_secret: "myregistrysecret"
        registry_gui_registry_image: "registry:2"
        registry_gui_registry_ui_image: "joxit/docker-registry-ui:latest"
        registry_gui_registry_ui_container_name: "registry-ui"
        registry_gui_nginx_lb_container_name: "registry-nginx"
        registry_gui_cert_dir: "/etc/registry/certs"
        registry_gui_nginx_config_dir: "/etc/registry/nginx"
        registry_gui_local_pull_secret_path: "/etc/registry/auth/htpasswd"
```
## Dependencies
- Ansible 2.12+
- `containers.podman` collection
- `redhatci.ocp.setup_mirror_registry`
- `ansible.posix` collection (for `firewalld`)

## Supported Platforms
- RHEL 9


License
-------

Apache