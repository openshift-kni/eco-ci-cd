# OCP upgrade

Upgrade the current cluster to one OCP release. A **hop** means one such upgrade step; repeat the role for a multi-step upgrade. The role does not plan the full upgrade path.

## Required settings

Set these for every upgrade:

```yaml
kubeconfig: /path/to/kubeconfig   # on the bastion
ocp_hop_target: "4.21"           # target major.minor
ocp_upgrade_channel: stable-4.21 # required for all modes; used to query the graph
```

## Choose a release

Choose one option:

1. **Cincinnati graph (default):** Set only the required settings. The role selects the highest target z-stream with an edge from the current release on `ocp_upgrade_channel`. It fails if no edge is found. Conditional edges may still be rejected by the cluster.
2. **Latest accepted stable:** Set `ocp_hop_use_latest_stable: true`. This selects the latest accepted stable z-stream for `ocp_hop_target` from the release stream; it does not check for a graph edge.
3. **Specific release image:** Set `ocp_hop_image: <release-image>`. The role checks that the image matches `ocp_hop_target` and pins it by digest. If registry authentication is required, set `ocp_upgrade_pull_secret` to the pull secret JSON.

Do not set `ocp_hop_image` together with `ocp_hop_use_latest_stable`. Automatic graph and stable-stream selection targets amd64.

## Optional settings

- `ocp_hop_then`: In graph mode, select an upgrade that also has a graph edge to this next major.minor, for example `"4.22"`. This does not perform the next upgrade.
- `ocp_hop_allow_not_recommended: true`: Pass `--allow-not-recommended` to `oc adm upgrade`.
- `ocp_upgrade_force: true`: Pass `--allow-upgrade-with-warnings --force`. Both override options default to `false`; use them only when the risks are understood.
- `artifacts_folder`: Existing directory on the bastion for the upgrade summary; defaults to `/artifacts`.

## Run

Save the required settings and chosen options in `upgrade-vars.yml`, then run from the repository root with an inventory containing `bastion`:

```shell
ansible-playbook -i inventory playbooks/compute/ocp-upgrade.yml -e @upgrade-vars.yml
```

The role waits for completion and writes a summary such as `ocp-upgrade-hop-4-21.json` in `artifacts_folder`.
