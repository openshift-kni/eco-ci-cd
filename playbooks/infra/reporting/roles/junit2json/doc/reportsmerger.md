# Filter plugin `reportsmerger`

Aggregates N JSON reports into 1 consolidated test report.
Supports several strategies for different scenarios.

## Usage

```yaml
---
- name: merge files with default strategy into variable my_var
  ansible.builtin.set_fact:
    my_var: "{{ ['f1.json', 'f2.json'] | reportsmerger }}"

- name: merge files with specific strategy and output to file
  ansible.builtin.set_fact:
    result_path: "{{ ['f1.json', 'f2.json'] | reportsmerger(strategy='normal', output='result.json') }}"
```

## Strategies

The `reportsmerger` filter provides multiple optimization strategies to handle different scenarios efficiently:

### `normal` (Default)

**Use case**: Standard merging for typical file sizes and counts  
**Behavior**: Sequential processing with full data loading and validation  
**Memory usage**: Moderate - loads all files into memory  
**Performance**: Baseline performance, backward compatible  
**Best for**: Small to medium files (< 100MB), moderate file counts (< 50 files)

```yaml
- name: standard merge
  ansible.builtin.set_fact:
    merged: "{{ report_files | reportsmerger(strategy='normal') }}"
```

### `large`

**Use case**: Memory-efficient processing of large individual files  
**Behavior**: Streaming aggregation with immediate memory cleanup  
**Memory usage**: Low - processes files one at a time with explicit cleanup  
**Performance**: Slightly slower due to aggressive cleanup, but memory-safe  
**Best for**: Large files (> 100MB), memory-constrained environments

```yaml
- name: merge large files efficiently
  ansible.builtin.set_fact:
    merged: "{{ large_report_files | reportsmerger(strategy='large') }}"
```

### `many`

**Use case**: Fast processing of many files using parallel I/O  
**Behavior**: Parallel file processing with thread-safe accumulation  
**Memory usage**: Moderate to high - loads multiple files concurrently  
**Performance**: Fastest for I/O-bound scenarios (max 4 threads)  
**Best for**: Many files (> 50), fast storage, sufficient memory

```yaml
- name: parallel processing of many files
  ansible.builtin.set_fact:
    merged: "{{ many_report_files | reportsmerger(strategy='many') }}"
```

### `shallow`

**Use case**: Statistics-focused operations without detailed test suite data  
**Behavior**: Lazy loading of test suites - only loads when accessed  
**Memory usage**: Very low - defers test suite loading until needed  
**Performance**: Fastest for stats-only operations  
**Best for**: Dashboard summaries, quick statistics, when test suite details aren't immediately needed

```yaml
- name: get quick statistics without loading full test suites
  ansible.builtin.set_fact:
    stats: "{{ report_files | reportsmerger(strategy='shallow') }}"
    
# Test suites are loaded only when accessed:
- debug:
    msg: "Total tests: {{ stats.tests }}, Total suites: {{ stats.test_suites | length }}"
```

### `complex`

**Use case**: Lightweight merging that excludes heavy test case details  
**Behavior**: Custom JSON parsing that strips detailed test case data during loading  
**Memory usage**: Low - removes test case details, keeps suite metadata  
**Performance**: Good for complex schemas with heavy test case data  
**Best for**: Files with extensive test case details, when only suite-level information is needed

```yaml
- name: lightweight merge excluding test case details
  ansible.builtin.set_fact:
    lightweight: "{{ complex_report_files | reportsmerger(strategy='complex') }}"
```

## Strategy Selection Guide

| Scenario                  | Strategy  | Reason                                  |
| ------------------------- | --------- | --------------------------------------- |
| < 50 files, < 100MB each  | `normal`  | Balanced performance and compatibility  |
| Large files (> 100MB)     | `large`   | Memory-efficient streaming              |
| Many files (> 50)         | `many`    | Parallel I/O processing                 |
| Stats/dashboards only     | `shallow` | Lazy loading for performance            |
| Heavy test case data      | `complex` | Strips unnecessary details              |

## Output Options

All strategies support writing output directly to a file:

```yaml
- name: merge and save to file
  ansible.builtin.set_fact:
    result_path: "{{ files | reportsmerger(strategy='large', output='/tmp/merged.json') }}"
    # Returns the file path, not the data
```
