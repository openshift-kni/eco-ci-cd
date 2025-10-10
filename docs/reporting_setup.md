# Overview

> **📖 For complete setup instructions and build system documentation, see the [build utilities README](../build.util/README.md)**

## Requirements

- Python (version: `>=3.11`)
- GNU make (version: `>=4.0.0`)
  - on Mac, make an alias: `alias make=gmake`

## Build automation files

- `build.util/makefile.mk` - Main build system (see [README](../build.util/README.md) for setup)
- `vars.mk` - Generated configuration file
- `.env` - Generated environment variables

## Contents Overview

The CI system should run reporting playbook.
It should generate test results in JUnit format.

The reporting happens in 4 steps:

| Stage | Description                           | Role                                                          |
| ----- | ------------------------------------- | ------------------------------------------------------------- |
| 1.    | Test Data (JUnit to JSON)             | [`junit2json`](playbooks/roles/junit2json/)                   |
| 2.    | CI Metadata generation                | [`report_metadata_gen`](playbooks/roles/report_metadata_gen/) |
| 3.    | Test Data & CI Metadata to event file | [`report_combine`](playbooks/roles/report_combine/)           |
| 4.    | Send event to collection system       | [`report_send`](playbooks/roles/report_send/)                 |

The above roles are located under `playbooks/roles/`

| File                                                                         | Function                      |
| ---------------------------------------------------------------------------- | ----------------------------- |
| [`playbooks/report-send.yml`](playbooks/report-send.yml)                     | reporting playbook            |
| [`playbooks/test-report-send.yml`](playbooks/test-report-send.yml)           | reporting test playbook       |
| [`playbooks/test-time-conversion.yml`](playbooks/test-time-conversion.yml)   | time conversion test playbook |
| [`playbooks/fixtures/dci/`](playbooks/fixtures/dci/)                         | test data for DCI CI          |
| [`playbooks/fixtures/jenkins/`](playbooks/fixtures/jenkins/)                 | test data for Jenkins CI      |
| [`playbooks/fixtures/time-conversion/`](playbooks/fixtures/time-conversion/) | test data of time-conversions |

The above files are in the branch `reporting-playbooks`

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



### Running Ansible testing playbooks

### Using the container
