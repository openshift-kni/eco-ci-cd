# ocp_operator_deployment unit tests

This role is mostly live-infrastructure orchestration (OLM install via
`redhatci.ocp.olm_operator`, CatalogSource/Secret/IDMS via
`kubernetes.core.k8s*`), so unlike the other roles' single `tests/`
directory, coverage here is split into **two independent suites** that each
follow the `ocp_version_facts`-style data-driven pattern:

```
tests/
├── README.md
├── validation/            # full-role, validation/routing fixtures only
│   ├── test.yml
│   ├── run_tests.py
│   └── cases/
└── operator_group_spec/   # task-level, resolve_operator_group_spec.yml only
    ├── test.yml
    ├── run_tests.py
    └── cases/
```

## `validation/` - full-role fixtures

`validation/test.yml` runs the whole role via `include_role`. This is only
safe for fixtures that abort in `tasks/main.yml`'s upfront validation/
routing before ever reaching a live call:

- missing/empty `ocp_operator_deployment_operators`, undefined
  `ocp_operator_deployment_version` (top-of-file `assert`)
- a `stage`-catalog operator missing `ocp_operator_deployment_stage_repo_image`/
  `_stage_cs_secret` (stage-specific `assert`)
- an operator routed to the `pre_ga` or `brew` catalog - `tasks/deploy_pre_ga.yaml`
  and `tasks/deploy_brew.yaml` are unimplemented stubs (unconditional
  `ansible.builtin.fail`) as of this writing, so routing to either always
  fails. **Rewrite `cases/routed-to-pre-ga-stub.yml` /
  `cases/routed-to-brew-stub.yml` once those task files are actually
  implemented** - they're not testing real behavior, just documenting that
  the stub trips.

Remember `stage`/`prod`/`pre_ga`/`brew` in `vars/main.yml` are role vars
resolving to literal catalog-name strings (e.g. `redhat-operators-stage`) -
fixtures must set `item.catalog` to that literal string, not the bare word.

There's deliberately no "happy path" fixture here (every case is
`expect_failure: true`). `tasks/main.yml`'s "Deploy operator" step is
unconditional - any operator list that passes the upfront `assert` always
reaches `deploy_operator.yaml`'s `include_role: redhatci.ocp.olm_operator`,
whose first live task (`Check CatalogSource is Ready`) has hardcoded
`retries: 60`/`delay: 10`. A fixture that gets that far would hang for
~10 minutes per run without a real cluster, not fail fast - there's no
valid input that both satisfies the role's own validation and avoids that
call. Genuine success-path coverage for this role's pure logic lives in
`operator_group_spec/` instead.

Run: `./validation/run_tests.py`

## `operator_group_spec/` - task-level fixtures

`tasks/deploy_operator.yaml`'s only pure logic - resolving
`operator_group_spec_config` from `operator_item.og_spec` (or defaulting to
`{targetNamespaces: [operator_item.nsname]}`) - sits immediately before an
unconditional `include_role: redhatci.ocp.olm_operator` (live, external).
It's extracted into its own file, `tasks/resolve_operator_group_spec.yml`,
specifically so it can be tested without an `include_role` at all:
`operator_group_spec/test.yml` does `include_tasks` on that file directly
with `operator_item` pre-set, and asserts the resulting
`operator_group_spec_config`.

Run: `./operator_group_spec/run_tests.py`

## What's not covered

Everything else in this role - stage CatalogSource/Secret creation
(`deploy_stage.yaml`), the actual OLM install
(`redhatci.ocp.olm_operator`), and default-config application
(`kubernetes.core.k8s`) - is live-cluster orchestration with no
register/guard seam to mock cheaply. That needs a live/integration test,
not a unit test.
