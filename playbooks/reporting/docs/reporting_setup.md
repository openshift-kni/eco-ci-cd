# Overview

## Requirements

- Python (version: `>=3.11`)
- GNU make (version: `>=4.0.0`)

## Build automation files

- on Mac, create an alias:

    ```bash
    alias make=gmake
    ```

- clone helper repository `build-util` under tree root:

    ```bash
    pushd $PWD 2>&1 >/dev/null
    cd $(git )
    test -d build.util || git clone https://github.com/mvk/eco-ci-cd-build-util.git build.util
    popd 2>&1 >/dev/null
    ```

Refer to `build-util`'s [README](https://github.com/mvk/eco-ci-cd-build-util/README.md) for more details

- `.env` - Environment variables, most minimal should be:

    ```bash
    export MAKEFLAGS="-f build.util/makefile.mk"
    ```

  - **NOTE:** source this file before running make commands.

- `build.util/makefile.mk` - main makefile
- `vars.mk` - local overrides file for the Makefile defaults

## Contents Overview

The CI system should run reporting playbook.
It should generate test results in JUnit format.

The reporting happens in 4 steps:

| Stage | Function                             | Role                                                            |
| ----- | ------------------------------------ | --------------------------------------------------------------- |
| 1.    | Convert Test Data from JUnit to JSON | [`junit2json`](playbooks/reporting/roles/junit2json)            |
| 2.    | Generate CI Metadata                 | [`metadata_gen`](playbooks/reporting/roles/report_metadata_gen) |
| 3.    | Merge CI + Test data in 1 file       | [`combine`](playbooks/reporting/roles/report_combine)           |
| 4.    | Send event to collection system      | [`send`](playbooks/reporting/roles/report_send)                 |

The above roles are located under `playbooks/reporting/roles`

| File                                                                         | Function                      |
| ---------------------------------------------------------------------------- | ----------------------------- |
| [`report-send.yml`](playbooks/reporting/report-send.yml)                     | reporting playbook            |
| [`test-report-send.yml`](playbooks/reporting/test-report-send.yml)           | reporting test playbook       |
| [`test-time-conversion.yml`](playbooks/reporting/test-time-conversion.yml)   | time conversion test playbook |
| [`fixtures/dci/`](playbooks/reporting/fixtures/dci/)                         | test data for DCI CI          |
| [`fixtures/jenkins/`](playbooks/reporting/fixtures/jenkins/)                 | test data for Jenkins CI      |
| [`fixtures/time-conversion/`](playbooks/reporting/fixtures/time-conversion/) | test data of time-conversions |


## Testing

### Setup

1. Refer to [eco-ci-cd-build-util](https://github.com/mvk/eco-ci-cd-build-util)
2. Back to `eco-ci-cd` repo root
3. Run:

```bash
source .env
make bootstrap
```

### Running Python tests

```bash
source .env
make run-python-tests
```

### Running Ansible testing playbooks

```bash
source .env
make run-all-e2e-tests

```

## Container

The ansible code in this repository is expected to be packaged and run as container image.

- The CI publishes the image to [Quay.io](quay.io) registry under a `<namespace>` as image `eco-ci-cd`.
- The default namespace is defined in `makefile.mk` as `NAMESPACE ?= telcov10n-ci`.
- During the development it is convenient to use personal namespace.
  - You can override it you in `vars.mk` file by defining that variable

### Using the container

#### Directly

TBD: env variables and volumes/mounts to have for the container to work properly

#### Using CI
