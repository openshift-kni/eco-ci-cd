# container_image_mirror unit tests

Data-driven unit tests for the `container_image_mirror` role, following the
same pattern as `playbooks/roles/ocp_version_facts/tests/`. Each fixture in
`cases/` supplies role input vars (and, for the guarded live calls, their
mocked results); `test.yml` runs the role once and asserts the resulting
facts.

## Layout

```
mock/
├── README.md
├── run_tests.py       # thin wrapper around tests/lib/ansible_role_test_runner.py
├── test.yml           # generic playbook: run the role, assert expected_facts
└── cases/
```

## Running

```bash
./playbooks/roles/container_image_mirror/tests/mock/run_tests.py
```

Or run a single case directly, from the repo root:

```bash
ansible-playbook playbooks/roles/container_image_mirror/tests/mock/test.yml \
  -e "@playbooks/roles/container_image_mirror/tests/mock/cases/mirror-happy-path.yml"
```

## Mocking the live calls

Unlike the other roles' test suites, `mirror.yaml`'s `skopeo copy` task and
`remove.yaml`'s `file: state: absent` task are **looped** over
`container_image_mirror_images` with `register: _mirror_result` /
`register: _remove_result`. The `X is not defined` guard used elsewhere in
this repo's role tests doesn't work on a looped task: the register becomes
defined after the *first* iteration, so a same-var guard would skip every
iteration after the first for the wrong reason (stale state, not
intentional mocking).

Instead, these two tasks (plus `mirror.yaml`'s registry tag-list `uri`
check, `_image_check`, unused downstream but guarded for the same reason)
are guarded by a dedicated boolean:

```yaml
when: not (container_image_mirror_test_mode | default(false))
```

Fixtures that want to skip the live `skopeo`/`file` calls set
`container_image_mirror_test_mode: true` and pre-seed the whole result
shape directly, e.g.:

```yaml
container_image_mirror_test_mode: true
_mirror_result:
  results:
    - rc: 0
      image_item: {source: "...", dest: "..."}
```

The downstream summary-building (`_mirror_success`/`_mirror_failed`) and
fail-if-any-failed logic then run unmodified against that pre-seeded value.

## Real (unmocked) local-disk operations

Pull-secret staging (`ansible.builtin.copy`/`file`) runs under
`connection: local` against a real scratch path
(`container_image_mirror_pull_secret_path`) - no guard needed, these aren't
network/registry calls. `cases/pull-secret-enabled-happy-path.yml` exercises
this for real and uses `test.yml`'s optional
`assert_pull_secret_cleaned_up: true` extension to confirm the role's own
cleanup step removed the staged file.

Whether the role's `skopeo copy`/registry tag-list calls actually reach a
real registry is **not** covered here - see `../integration/README.md` for
that.

## Adding a case

Drop a new file in `cases/`, run `run_tests.py`, done.
