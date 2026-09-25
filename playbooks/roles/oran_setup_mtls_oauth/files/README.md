# oran_setup_mtls_oauth files

## oran-realm.json (NOT committed — supplied at runtime)

The Keycloak `oran` realm export is deliberately **not** stored in git: it
contains the `o2ims-client` / `smo-client` secrets and the realm signing keys
(RSA private keys).

- **In CI (openshift/release):** the realm export is stored in Vault and synced
  to the `test-credentials` namespace. The `oran-setup` step mounts it and
  passes `oran_realm_json_file=<mounted path>` to the playbook.
- **Standalone:** drop your realm export at
  `roles/oran_setup_mtls_oauth/files/oran-realm.json` (the default
  `oran_realm_json_file`), or pass `oran_realm_json_file=/path/to/oran-realm.json`.

The `o2ims-client` and `smo-client` secrets consumed by the mock-SMO deployment
and the `oauth-client-secrets` Secret are **derived from this file at runtime**
(`tasks/main.yaml`), so the realm export is the single source of truth and no
secret is hard-coded in the templates.
