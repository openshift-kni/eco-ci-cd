# ocp_version_facts unit tests

Data-driven unit tests for the `ocp_version_facts` role. Each fixture in
`cases/` supplies role input vars plus the facts the role is expected to
produce; `test.yml` runs the role once and asserts the actual facts match.

## Layout

```
tests/
├── README.md
├── run_tests.py       # runner (python3, stdlib only): one ansible-playbook invocation per case
├── test.yml           # generic playbook: run the role, assert expected_facts
└── cases/
```

Each `cases/*.yml` file is a plain vars file with:

- the role's input vars (`ocp_version_facts_release`, and optionally
  `ocp_version_facts_query` / `image_age_days` — see "Mocking the network
  lookup" below)
- `expected_facts`: a dict of `fact_name: expected_value` (compared as
  strings)
- `expected_undefined_facts`: a list of fact names that must remain unset
  for this case (e.g. `ocp_version_facts_dev_version` for a stable release)
- `expect_failure: true` for cases that should make the role's own
  `assert`/`fail` tasks trip (bad input, etc.) — omit it
  (defaults to `false`) for cases that should succeed

## Running

```bash
./playbooks/roles/ocp_version_facts/tests/run_tests.py
```

`run_tests.py` is a plain Python 3.10+ script (no `pip install` needed) that
finds the repo root itself, so it can be run from anywhere. It runs each
fixture in its own `ansible-playbook` process — see the module docstring for
why — printing a `PASS`/`FAIL` line as each case finishes, followed by a
summary. Failing cases keep their captured `ansible-playbook` output in a
temp file, whose path is printed alongside the failure.

Or run a single case directly, from the repo root (needed so `ansible.cfg`'s
`roles_path` resolves):

```bash
ansible-playbook playbooks/roles/ocp_version_facts/tests/test.yml \
  -e "@playbooks/roles/ocp_version_facts/tests/cases/release-candidate.yml"
```

## `null` vs. undefined

`expected_facts` and `expected_undefined_facts` mean different things and
the role isn't consistent about which it uses:

- `ocp_version_facts_dev_version` is only ever `set_fact`'d on dev builds -
  on a stable release the task is skipped, so the var is genuinely
  undefined. Use `expected_undefined_facts` for this.
- `ocp_version_facts_z_stream` is always set once (from the parsed version),
  then explicitly reset to `null` on dev builds - it's defined, just empty.
  Put `ocp_version_facts_z_stream: null` in `expected_facts` for those
  cases, not in `expected_undefined_facts` (a `varnames` lookup still finds
  it, since it exists with value `None`).

## Mocking the network lookup

When `ocp_version_facts_release` is 7 characters or fewer (a minor release
like `4.17` or an exact version like `4.17.9`), the role resolves it against
live release-stream/registry APIs in `tasks/latest_release.yml`. That's out
of scope for a unit test — it's covered by the `ocp_version_facts_query is
not defined` guard already built into that file: pre-setting
`ocp_version_facts_query` (and `image_age_days`, which the real lookup would
otherwise populate) skips the HTTP calls entirely and lets the rest of the
role's fact-setting logic be exercised deterministically. See
`cases/minor-release-mocked.yml` and `cases/image-age-exceeded.yml`.

Whether the role's `uri` calls actually talk to `quay.io` and the release
streams correctly is **not** covered here — that needs a live/integration
test, not a unit test.

## Adding a case

Drop a new file in `cases/`, run `run_tests.py`, done — no changes needed to
`test.yml` or the runner.
