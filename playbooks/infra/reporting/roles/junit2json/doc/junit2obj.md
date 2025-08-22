# Filter plugin `junit2obj`

Converts JUnit to JSON

## Requirements

- `lxml`

## Usage

A task list can use the filter as follows:

```yaml
---
# convert the report to JSON
- name: convert junit XML data 2 json
  ansible.builtin.set_fact:
    my_json: "{{ xml_data | junit2obj }}"

```
