# Filter plugin `reportsmerger`

Aggregates N JSON reports into 1 consolidated test report.

## Usage

```yaml
---
- name: merge files into variable my_var
  ansible.builtin.set_fact:
    my_var: "{{ ['f1.json', 'f2.json'] | reportsmerger }}"

- name: merge files and output to file
  ansible.builtin.set_fact:
    result_path: "{{ ['f1.json', 'f2.json'] | reportsmerger(output='result.json') }}"
```

## Parameters

- **filenames** (required): List of JSON file paths to merge
- **output** (optional): File path to write merged data. When specified, returns the file path instead of the merged data

## Examples

```yaml
# Basic merge - returns merged data
- name: merge test reports
  ansible.builtin.set_fact:
    merged_data: "{{ report_files | reportsmerger }}"

# Save to file - returns file path
- name: merge and save to file
  ansible.builtin.set_fact:
    output_file: "{{ report_files | reportsmerger(output='/tmp/merged.json') }}"

# Access merged statistics
- debug:
    msg: "Total tests: {{ merged_data.tests }}, Failures: {{ merged_data.failures }}"
```

## Output Format

The merged report contains:

- **time**: Total execution time from all test suites (float)
- **tests**: Total number of tests (int)
- **failures**: Total number of failures (int)
- **errors**: Total number of errors (int)
- **skipped**: Total number of skipped tests (int)
- **test_suites**: Combined list of all test suites from input files (list)
- **schema_version**: Schema version (string)
