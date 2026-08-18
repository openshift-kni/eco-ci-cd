# collect_metrics unit tests

Data-driven unit tests for the `collect_metrics` role, following the same
pattern as `playbooks/roles/ocp_version_facts/tests/`. Each fixture in
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

- the role's input vars (`collect_metrics_ci_lane`, `collect_metrics_list`,
  `collect_metrics_output_file`, and whichever kubeconfig vars the selected
  categories need), plus mocked `kubernetes.core.k8s_info`/
  `containers.podman.podman_image_info` register vars for the categories
  under test — see "Mocking the live calls" below
- `expected_facts`: a dict of `fact_name: expected_value` (compared as
  strings) — the role's single externally-visible output is the
  `collect_metrics_attributes` semicolon-delimited string, so most fixtures
  only assert that one fact
- `expected_undefined_facts`: a list of fact names that must remain unset
- `expect_failure: true` for cases that should make the role's own
  `assert` tasks trip

## Running

```bash
./playbooks/roles/collect_metrics/tests/run_tests.py
```

Or run a single case directly, from the repo root:

```bash
ansible-playbook playbooks/roles/collect_metrics/tests/test.yml \
  -e "@playbooks/roles/collect_metrics/tests/cases/general-ocp-happy-path.yml"
```

## Mocking the live calls

Every metric category's live query is a single, unlooped `register:`'d task
(`_cluster_version`, `_infra`, `_worker_nodes`, `_sriov_sub`, `_talm_sub`,
etc. — one register var per category file, see each `tasks/*.yml`), now
guarded the same way `ocp_version_facts/tasks/latest_release.yml` guards its
`uri` call: `when: <register> is not defined`. Pre-seeding the register var
in a fixture (as the shape `kubernetes.core.k8s_info`/`podman_image_info`
would have returned it, e.g. `{resources: [...]}` or `{images: [...]}`)
skips the live call and exercises only the deterministic string-building
logic downstream.

`containers_digests.yml`'s `image_facts` guard is only safe for fixtures
with a single-item `collect_containers_list` — `tasks/main.yml` loops
`include_tasks: containers_digests.yml` per image, and since each inclusion
re-runs the guarded task, a second loop iteration would see `image_facts`
already defined from the first and skip its own live call. Don't add a
multi-image fixture without addressing that; the existing fixtures only
ever exercise one image at a time.

**The N/A/rescue path needs no guard or mocking at all.** Every category is
wrapped in `block/rescue` without `failed_when: false`, so pointing a
fixture's kubeconfig at a nonexistent path makes the live `k8s_info` call
fail fast (local file read error) into the `rescue:` branch deterministically
— see `cases/operators-na-rescue.yml`.

Whether the role's `k8s_info`/`podman_image_info` calls actually reach a
live cluster or registry correctly is **not** covered here — that needs a
live/integration test.

## Adding a case

Drop a new file in `cases/`, run `run_tests.py`, done.
