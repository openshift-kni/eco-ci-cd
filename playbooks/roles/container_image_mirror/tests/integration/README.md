# container_image_mirror live integration tests

Live counterpart to `../mock/` (the mocked unit tests). Where the unit
tests set `container_image_mirror_test_mode: true` and pre-seed
`_mirror_result`/`_remove_result` to skip the role's real `skopeo copy`,
registry tag-list `uri` check, and file removal, these tests let all three
run for real - see `../mock/README.md`'s "Mocking the live calls" section
for why that gap existed.

## Layout

```
integration/
├── README.md
├── run_tests.py       # standalone orchestrator - see "Why not tests/lib/ansible_role_test_runner.py" below
├── test.yml            # like ../mock/test.yml, plus real registry post-checks
└── cases/
```

## What's real here

- **Source**: a real, already-running registry -
  `registry.access.redhat.com/ubi9/ubi-micro:latest` - reached over the
  network exactly like production traffic. This suite doesn't control or
  stand up the source side.
- **Destination**: a single ephemeral registry instance that `run_tests.py`
  starts for the whole run - the plain `registry` binary from the
  [distribution/distribution](https://github.com/distribution/distribution)
  project (this is the same server the `registry:2` container image runs).
  It's run as a plain background process, not a container: nested
  podman/docker inside a Prow pod risks the same arbitrary-UID /
  storage-driver failures already fixed once for Ansible's own tmp dir (PR
  #641). A single static binary sidesteps that entirely - no root, no
  container engine, no image bloat.
- **`mirror`**: the role's real `skopeo copy` pushes into that local
  instance; `test.yml` then does a real `GET .../tags/list` to confirm the
  image actually landed.
- **`remove`**: `test.yml` first mirrors a seed image into the same local
  instance for real (there has to be something real to delete), then runs
  the role under test in `remove` mode, then does a real `GET
  .../tags/list` expecting `404` to confirm it's actually gone.

### Why `remove` needs `container_image_mirror_become_override: false`

`remove.yaml`'s file-deletion task escalates via `become` because in
production the registry's storage is written by a container runtime and
often isn't owned by the SSH-connecting ansible user. Here, the same UID
that starts the local registry also runs the deletion - there's no
privilege boundary to cross, and Prow's arbitrary injected UID has no
`/etc/passwd` entry for `sudo` to authenticate against anyway.
`container_image_mirror_become_override` is an internal knob read inline in
`remove.yaml` (`| default(true)`) - it is **not** a documented role
variable; only this suite's `remove-happy-path.yml` sets it.

## Why not `tests/lib/ansible_role_test_runner.py`

That runner's contract is one fresh `ansible-playbook` process per fixture,
each a self-contained unit with no shared state - deliberate, so one case's
`set_fact` state can't bleed into the next (see its docstring). Integration
tests need the opposite for the registry: one process, started once,
shared across every case, torn down after the whole run. `run_tests.py`
here is a small standalone script for that reason; it still reuses
`expects_failure()` from the shared runner for the `expect_failure: true`
fixture convention.

## Requirements

- `skopeo` on `PATH` (installed in the `eco-ci-cd` image via the
  `Containerfile`; install it locally to run this outside a container)
- Outbound network access to `registry.access.redhat.com` (mirror source)
  and `github.com` (to fetch the pinned `registry` binary release, cached
  under `/tmp/container-image-mirror-it/` after the first run)
- No root, no sudo, no container engine

## Running

```bash
./playbooks/roles/container_image_mirror/tests/integration/run_tests.py
```

## Adding a case

Drop a new file in `cases/`, run `run_tests.py`. Set
`assert_dest_tags_present: true` / `assert_dest_tags_absent: true` to get
the real post-check, and `_seed_images` if the case needs something
mirrored in first.
