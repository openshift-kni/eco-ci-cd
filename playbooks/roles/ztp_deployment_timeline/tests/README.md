# ztp_deployment_timeline unit tests

Data-driven unit tests for the `ztp_deployment_timeline` role, following the
same pattern as `playbooks/roles/ocp_version_facts/tests/`. Each fixture in
`cases/` supplies role input vars plus the facts the role is expected to
produce; `test.yml` runs the role once and asserts the actual facts match.

## Layout

```
tests/
├── README.md
├── run_tests.py       # thin wrapper around tests/lib/ansible_role_test_runner.py
├── test.yml           # generic playbook: run the role, assert expected_facts
└── cases/
```

Each `cases/*.yml` file is a plain vars file with:

- the role's input vars (`spoke_cluster`, `hub_kubeconfig`, optionally
  `generate_detailed_summary` and `ansible_date_time`), plus the 9 mocked
  `kubernetes.core.k8s_info` register vars — see "Mocking the k8s_info
  queries" below
- `expected_facts`: a dict of `fact_name: expected_value` (compared as
  strings)
- `expected_undefined_facts`: a list of fact names that must remain unset
- `expected_events_count`: optional, asserts `ztp_deployment_timeline_events
  | length` (the events list is a list of dicts, too unwieldy to push
  through the string-compare `expected_facts` mechanism)
- `expect_failure: true` for cases that should make the role's own
  `assert`/`fail` tasks trip — omit it (defaults to `false`) for cases that
  should succeed

## Running

```bash
./playbooks/roles/ztp_deployment_timeline/tests/run_tests.py
```

Or run a single case directly, from the repo root:

```bash
ansible-playbook playbooks/roles/ztp_deployment_timeline/tests/test.yml \
  -e "@playbooks/roles/ztp_deployment_timeline/tests/cases/happy-path-ai.yml"
```

## Mocking the k8s_info queries

The role issues 9 live `kubernetes.core.k8s_info` queries against
`hub_kubeconfig` across `tasks/main.yml` (ClusterInstance, ManagedCluster,
AgentClusterInstall, ImageBasedInstall, ClusterGroupUpgrade) and
`tasks/collect_events.yml` (InfraEnv, Agent, ManifestWork, Policy). None of
these tasks are guarded with an `is not defined` check (unlike
`ocp_version_facts/tasks/latest_release.yml`'s `uri` call) — the query tasks
always run. Mocking instead relies on Ansible's variable precedence: extra
vars (`-e "@cases/<name>.yml"`) always outrank a task's `register:` result,
so pre-seeding e.g. `clusterinstance_query` in a fixture (as a plain
`{resources: [...]}` dict) makes every later reference to that var resolve
to the fixture's value regardless of what the real (and, with
`hub_kubeconfig` pointing at `/fake/kubeconfig`, failing) `k8s_info` call
registers. `failed_when: false` on each query keeps that failure from
aborting the play, so only the deterministic fact-derivation logic
downstream (deployment-method detection, timestamp extraction, duration
math, event collection/sorting, fail-fast validation) is actually
exercised.

Fixtures should pre-seed all 9 register vars even when a query wouldn't
normally run for a given deployment method (e.g. `infraenv_query`/
`agents_query` for an IBI fixture) — the point of mocking is to guarantee no
live call is attempted, not just to make the happy path deterministic.

Whether the role's `k8s_info` calls actually reach a hub cluster correctly
is **not** covered here — that needs a live/integration test.

`tasks/generate_detailed_summary.yml` reads `ansible_date_time.iso8601` for
"time since ready" math. `test.yml` runs with `gather_facts: false` for
determinism, so fixtures exercising `generate_detailed_summary: true` must
pin `ansible_date_time: {iso8601: "<fixed timestamp>"}` as a plain var
rather than relying on the real wall clock.

## Adding a case

Drop a new file in `cases/`, run `run_tests.py`, done.
