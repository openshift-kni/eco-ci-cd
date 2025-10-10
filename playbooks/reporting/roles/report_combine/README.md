<!-- DOCSIBLE START -->

# 📃 Role overview

## report_combine

Description: Role to combine test reports and metadata into event structures for collectors

<details>
<summary><b>🧩 Argument Specifications in meta/argument_specs</b></summary>

### Key: main

**Description**: This role combines test report JSON and metadata JSON files into
collector-specific event structures. It supports multiple output formats
including Splunk HEC format and generic formats.

- **rc_report_path**
  - **Required**: True
  - **Type**: str
  - **Default**: none
  - **Description**: Path to the test report JSON file
  
- **rc_metadata_path**
  - **Required**: True
  - **Type**: str
  - **Default**: none
  - **Description**: Path to the metadata JSON file
  
- **rc_combined_event_path**
  - **Required**: False
  - **Type**: str
  - **Default**: {{ playbook_dir }}/combined-event.json
  - **Description**: Path where to save the combined event JSON file
  
- **rc_collector_format**
  - **Required**: False
  - **Type**: str
  - **Default**: splunk
  - **Description**: Format for the combined event structure
  
    - **Choices**:

      - splunk

      - generic

- **rc_event_source**
  - **Required**: False
  - **Type**: str
  - **Default**: {{ ansible_hostname }}
  - **Description**: Event source identifier

- **rc_event_time**
  - **Required**: False
  - **Type**: str
  - **Default**: `""`
  - **Description**: Event source identifier

- **rc_event_host**
  - **Required**: False
  - **Type**: str
  - **Default**: {{ ansible_hostname }}
  - **Description**: Event host identifier
  
- **rc_debug**
  - **Required**: False
  - **Type**: bool
  - **Default**: False
  - **Description**: Enable debug output
  
</details>

### Defaults

#### **These are static variables with lower priority**

#### File: `defaults/main.yml`

| Var          | Type         | Value       |Required    | Title       |
|--------------|--------------|-------------|-------------|-------------|
| [rc_report_path](defaults/main.yml#L6)   | str   | `` |    True  |  Path to the test report JSON file |
| [rc_metadata_path](defaults/main.yml#L7)   | str   | `` |    True  |  Path to the metadata JSON file |
| [rc_combined_event_path](defaults/main.yml#L10)   | str   | `{{ playbook_dir }}/output/combined-event.json` |    False  |  Path where to save the combined event JSON file |
| [rc_event_time](defaults/main.yml#L16)   | str   | `` |    False  |  Event time in epoch float format as string |
| [rc_event_source](defaults/main.yml#L13)   | str   | `{{ ansible_hostname }}` |    False  |  Event source identifier |
| [rc_event_host](defaults/main.yml#L14)   | str   | `{{ ansible_hostname }}` |    False  |  Event host identifier |
| [rc_event_sourcetype](defaults/main.yml#L15)   | str   | `_json` |    n/a  |  n/a |
| [rc_collector_format](defaults/main.yml#L18)   | str   | `splunk` |    False  |  Format for the combined event structure |
| [rc_supported_formats](defaults/main.yml#L19)   | list   | `['splunk', 'generic']` |    n/a  |  n/a |
| [rc_debug](defaults/main.yml#L24)   | bool   | `False` |    False  |  Enable debug output |
| [rc_test_data](defaults/main.yml#L27)   | dict   | `{}` |    n/a  |  n/a |
| [rc_meta_data](defaults/main.yml#L28)   | dict   | `{}` |    n/a  |  n/a |
| [rc_combined_event](defaults/main.yml#L29)   | dict   | `{}` |    n/a  |  n/a |

### Tasks

#### File: `tasks/validate-file.yml`

| Name | Module | Has Conditions |
| ---- | ------ | --------- |
| Gathering file stats for `{{ _rc_file_path }}` | `ansible.builtin.stat` | False |
| Validating file requirements for `{{ _rc_file_path }}` | `ansible.builtin.assert` | False |

#### File: `tasks/read-file.yml`

| Name | Module | Has Conditions |
| ---- | ------ | --------- |
| Validate the file exists, readable and non-empty | `ansible.builtin.include_tasks` | False |
| Read JSON file {{ _rc_file_item.path }} | `ansible.builtin.slurp` | False |
| Parse data as JSON from file {{ _rc_file_item.path }} | `ansible.builtin.set_fact` | False |
| Verify the data is not empty (mandatory={{ _rc_file_item.mandatory ¦ default(false) ¦ string }}) | `ansible.builtin.assert` | True |
| Print user note | `ansible.builtin.debug` | True |
| Print {{ _rc_file_item.name }} (verbosity>=3) | `ansible.builtin.debug` | False |

#### File: `tasks/main.yml`

| Name | Module | Has Conditions |
| ---- | ------ | --------- |
| Validate required parameters | `ansible.builtin.assert` | False |
| Read input files | `ansible.builtin.include_tasks` | False |
| Combine data using format-specific logic | `ansible.builtin.include_tasks` | False |
| Print combined event structure | `ansible.builtin.debug` | True |
| Ensure output directory exists | `ansible.builtin.file` | True |
| Write combined event to output file | `ansible.builtin.copy` | True |

#### File: `tasks/formats/splunk.yml`

| Name | Module | Has Conditions |
| ---- | ------ | --------- |
| Create basic event structure | `ansible.builtin.set_fact` | False |
| Set default metadata based event time | `ansible.builtin.set_fact` | True |
| Generate fallback event time if metadata does not have it | `ansible.builtin.set_fact` | True |
| Ensure rc_event_time can be converted to a float | `ansible.builtin.assert` | False |
| Create Splunk-specific event payload | `ansible.builtin.set_fact` | False |
| Print Splunk event structure | `ansible.builtin.debug` | True |

#### File: `tasks/formats/generic.yml`

| Name | Module | Has Conditions |
| ---- | ------ | --------- |
| Create generic event structure | `ansible.builtin.set_fact` | False |
| Add optional timestamp if available in metadata | `ansible.builtin.set_fact` | True |
| Print generic event structure | `ansible.builtin.debug` | True |

## Author Information

Red Hat CI

### License

Apache-2.0

### Minimum Ansible Version

2.14

### Platforms

- **EL**: ['8', '9']
- **Fedora**: ['37', '38', '39']

<!-- DOCSIBLE END -->
