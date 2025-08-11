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
| [rc_report_path](defaults/main.yml#L6)   | str   | `` |    n/a  |  n/a |
| [rc_metadata_path](defaults/main.yml#L7)   | str   | `` |    n/a  |  n/a |
| [rc_combined_event_path](defaults/main.yml#L10)   | str   | `{{ playbook_dir }}/output/combined-event.json` |    n/a  |  n/a |
| [rc_event_source](defaults/main.yml#L13)   | str   | `{{ rc_meta_data.ci.url ¦ default(ansible_hostname) }}` |    n/a  |  n/a |
| [rc_event_host](defaults/main.yml#L14)   | str   | `{{ splunk_url ¦ default(ansible_hostname) }}` |    n/a  |  n/a |
| [rc_event_sourcetype](defaults/main.yml#L15)   | str   | `_json` |    n/a  |  n/a |
| [rc_collector_format](defaults/main.yml#L18)   | str   | `splunk` |    n/a  |  n/a |
| [rc_supported_formats](defaults/main.yml#L19)   | list   | `['splunk', 'generic']` |    n/a  |  n/a |
| [rc_debug](defaults/main.yml#L24)   | bool   | `False` |    n/a  |  n/a |
| [rc_test_data](defaults/main.yml#L27)   | dict   | `{}` |    n/a  |  n/a |
| [rc_meta_data](defaults/main.yml#L28)   | dict   | `{}` |    n/a  |  n/a |
| [rc_combined_event](defaults/main.yml#L29)   | dict   | `{}` |    n/a  |  n/a |

### Tasks

#### File: `tasks/validate-file.yml`

| Name | Module | Has Conditions |
| ---- | ------ | --------- |
| Gathering file stats for {{ _rc_file_path }} | ansible.builtin.stat | False |
| Validating file requirements for {{ _rc_file_path }} | ansible.builtin.assert | False |

#### File: `tasks/read-file.yml`

| Name | Module | Has Conditions |
| ---- | ------ | --------- |
| Validate the file exists, readable and non-empty | ansible.builtin.include_tasks | False |
| Read JSON file {{ _rc_file_item.path }} | ansible.builtin.slurp | False |
| Parse data as JSON from file {{ _rc_file_item.path }} | ansible.builtin.set_fact | False |
| Verify the data is not empty (mandatory={{ _rc_file_item.mandatory ¦ default(false) ¦ string }}) | ansible.builtin.assert | True |
| Print user note | ansible.builtin.debug | True |
| Print {{ _rc_file_item.name }} (vebosity>=3) | ansible.builtin.debug | False |

#### File: `tasks/main.yml`

| Name | Module | Has Conditions |
| ---- | ------ | --------- |
| Validate required parameters | ansible.builtin.assert | False |
| Read input files | ansible.builtin.include_tasks | False |
| Combine data using format-specific logic | ansible.builtin.include_tasks | False |
| Print combined event structure | ansible.builtin.debug | True |
| Ensure output directory exists | ansible.builtin.file | True |
| Write combined event to output file | ansible.builtin.copy | True |

#### File: `tasks/formats/splunk.yml`

| Name | Module | Has Conditions |
| ---- | ------ | --------- |
| Create basic event structure | ansible.builtin.set_fact | False |
| Create Splunk-specific event payload | ansible.builtin.set_fact | False |
| Add optional timestamp if available in metadata | ansible.builtin.set_fact | True |
| Print Splunk event structure | ansible.builtin.debug | True |

#### File: `tasks/formats/generic.yml`

| Name | Module | Has Conditions |
| ---- | ------ | --------- |
| Create generic event structure | ansible.builtin.set_fact | False |
| Add optional timestamp if available in metadata | ansible.builtin.set_fact | True |
| Print generic event structure | ansible.builtin.debug | True |

## Task Flow Graphs

### Graph for `validate-file.yml`

```mermaid
flowchart TD
Start
classDef block stroke:#3498db,stroke-width:2px;
classDef task stroke:#4b76bb,stroke-width:2px;
classDef includeTasks stroke:#16a085,stroke-width:2px;
classDef importTasks stroke:#34495e,stroke-width:2px;
classDef includeRole stroke:#2980b9,stroke-width:2px;
classDef importRole stroke:#699ba7,stroke-width:2px;
classDef includeVars stroke:#8e44ad,stroke-width:2px;
classDef rescue stroke:#665352,stroke-width:2px;

  Start-->|Task| Gathering_file_stats_for__rc_file_path0[gathering file stats for  rc file path]:::task
  Gathering_file_stats_for__rc_file_path0-->|Task| Validating_file_requirements_for__rc_file_path1[validating file requirements for  rc file path]:::task
  Validating_file_requirements_for__rc_file_path1-->End
```

### Graph for `read-file.yml`

```mermaid
flowchart TD
Start
classDef block stroke:#3498db,stroke-width:2px;
classDef task stroke:#4b76bb,stroke-width:2px;
classDef includeTasks stroke:#16a085,stroke-width:2px;
classDef importTasks stroke:#34495e,stroke-width:2px;
classDef includeRole stroke:#2980b9,stroke-width:2px;
classDef importRole stroke:#699ba7,stroke-width:2px;
classDef includeVars stroke:#8e44ad,stroke-width:2px;
classDef rescue stroke:#665352,stroke-width:2px;

  Start-->|Include task| validate_file_yml0[validate the file exists  readable and non empty<br>include_task: validate file yml]:::includeTasks
  validate_file_yml0-->|Task| Read_JSON_file_____rc_file_item_path___1[read json file     rc file item path   ]:::task
  Read_JSON_file_____rc_file_item_path___1-->|Task| Parse_data_as_JSON_from_file_____rc_file_item_path___2[parse data as json from file     rc file item path<br>  ]:::task
  Parse_data_as_JSON_from_file_____rc_file_item_path___2-->|Task| Verify_the_data_is_not_empty__mandatory_____rc_file_item_mandatory___default_false____string____3[verify the data is not empty  mandatory     rc<br>file item mandatory   default false    string    <br>When: **rc file item mandatory is defined and  rc file<br>item mandatory   default false**]:::task
  Verify_the_data_is_not_empty__mandatory_____rc_file_item_mandatory___default_false____string____3-->|Task| Print_user_note4[print user note<br>When: **not   rc file item mandatory   default false   and<br>vars  rc file item name    length    0**]:::task
  Print_user_note4-->|Task| Print_____rc_file_item_name_____vebosity__3_5[print     rc file item name     vebosity  3 ]:::task
  Print_____rc_file_item_name_____vebosity__3_5-->End
```

### Graph for `main.yml`

```mermaid
flowchart TD
Start
classDef block stroke:#3498db,stroke-width:2px;
classDef task stroke:#4b76bb,stroke-width:2px;
classDef includeTasks stroke:#16a085,stroke-width:2px;
classDef importTasks stroke:#34495e,stroke-width:2px;
classDef includeRole stroke:#2980b9,stroke-width:2px;
classDef importRole stroke:#699ba7,stroke-width:2px;
classDef includeVars stroke:#8e44ad,stroke-width:2px;
classDef rescue stroke:#665352,stroke-width:2px;

  Start-->|Task| Validate_required_parameters0[validate required parameters]:::task
  Validate_required_parameters0-->|Include task| read_file_yml1[read input files<br>include_task: read file yml]:::includeTasks
  read_file_yml1-->|Include task| formats____rc_collector_format____yml2[combine data using format specific logic<br>include_task: formats    rc collector format    yml]:::includeTasks
  formats____rc_collector_format____yml2-->|Task| Print_combined_event_structure3[print combined event structure<br>When: **rc debug**]:::task
  Print_combined_event_structure3-->|Task| Ensure_output_directory_exists4[ensure output directory exists<br>When: **rc combined event path   length   0 and rc<br>combined event path   dirname   length   1**]:::task
  Ensure_output_directory_exists4-->|Task| Write_combined_event_to_output_file5[write combined event to output file<br>When: **rc combined event path   length   0**]:::task
  Write_combined_event_to_output_file5-->End
```

### Graph for `formats/splunk.yml`

```mermaid
flowchart TD
Start
classDef block stroke:#3498db,stroke-width:2px;
classDef task stroke:#4b76bb,stroke-width:2px;
classDef includeTasks stroke:#16a085,stroke-width:2px;
classDef importTasks stroke:#34495e,stroke-width:2px;
classDef includeRole stroke:#2980b9,stroke-width:2px;
classDef importRole stroke:#699ba7,stroke-width:2px;
classDef includeVars stroke:#8e44ad,stroke-width:2px;
classDef rescue stroke:#665352,stroke-width:2px;

  Start-->|Task| Create_basic_event_structure0[create basic event structure]:::task
  Create_basic_event_structure0-->|Task| Create_Splunk_specific_event_payload1[create splunk specific event payload]:::task
  Create_Splunk_specific_event_payload1-->|Task| Add_optional_timestamp_if_available_in_metadata2[add optional timestamp if available in metadata<br>When: **rc meta data job is defined and rc meta data job<br>created at is defined and rc meta data job created<br>at   length   0**]:::task
  Add_optional_timestamp_if_available_in_metadata2-->|Task| Print_Splunk_event_structure3[print splunk event structure<br>When: **rc debug**]:::task
  Print_Splunk_event_structure3-->End
```

### Graph for `formats/generic.yml`

```mermaid
flowchart TD
Start
classDef block stroke:#3498db,stroke-width:2px;
classDef task stroke:#4b76bb,stroke-width:2px;
classDef includeTasks stroke:#16a085,stroke-width:2px;
classDef importTasks stroke:#34495e,stroke-width:2px;
classDef includeRole stroke:#2980b9,stroke-width:2px;
classDef importRole stroke:#699ba7,stroke-width:2px;
classDef includeVars stroke:#8e44ad,stroke-width:2px;
classDef rescue stroke:#665352,stroke-width:2px;

  Start-->|Task| Create_generic_event_structure0[create generic event structure]:::task
  Create_generic_event_structure0-->|Task| Add_optional_timestamp_if_available_in_metadata1[add optional timestamp if available in metadata<br>When: **rc meta data job is defined and rc meta data job<br>created at is defined and rc meta data job created<br>at   length   0**]:::task
  Add_optional_timestamp_if_available_in_metadata1-->|Task| Print_generic_event_structure2[print generic event structure<br>When: **rc debug**]:::task
  Print_generic_event_structure2-->End
```

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
