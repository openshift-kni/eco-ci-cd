#!/bin/bash

# Prow Shared Context Management Script
# This script provides functions for managing shared context data in JSON format
# Meant to be sourced by other scripts
#
# USAGE EXAMPLES:
#
# 1. Source the script:
#    source scripts/prow_share_context.sh
#
# 2. Get/initialize the full context (creates empty {} if not exists):
#    context=$(get_prow_share_context)
#    echo "$context"  # Output: {}
#
#    # If you accidentally pass parameters, you'll get a warning but still get the context:
#    context=$(get_prow_share_context "mistaken.key" 2>/dev/null)  # Still returns {}
#    # stderr: Warning: get_prow_share_context() does not expect parameters...
#
# 3. Set values using dot notation for nested keys:
#    update_prow_share_context "deployment.ocp.version" "4.15"
#    update_prow_share_context "tests.unit.status" "passed"
#    update_prow_share_context "tests.unit.count" "25"
#    update_prow_share_context "tests.integration.status" "running"
#    update_prow_share_context "environment.cluster.name" "test-cluster-01"
#
# 4. Get specific values back:
#    version=$(get_prow_share_context_value "deployment.ocp.version")
#    echo "OCP Version: $version"  # Output: OCP Version: 4.15
#
#    status=$(get_prow_share_context_value "tests.unit.status")
#    echo "Unit test status: $status"  # Output: Unit test status: passed
#
#    # Trying to get a non-existing key will show error message:
#    nonexistent=$(get_prow_share_context_value "does.not.exist")
#    # Output to stderr: Error: Key 'does.not.exist' not found in context
#    # $nonexistent will be empty, function returns 1
#
#    # Calling without parameters shows error:
#    get_prow_share_context_value
#    # Output to stderr: Error: get_prow_share_context_value() requires a key parameter
#    # Output to stderr: Usage: get_prow_share_context_value "path.to.key"
#
#    # Calling with multiple parameters shows error:
#    get_prow_share_context_value "key1" "key2"
#    # Output to stderr: Error: get_prow_share_context_value() expects only one parameter (key)
#
# 5. Check if a path exists before using it:
#    if get_prow_share_context_value "tests.e2e.status" >/dev/null 2>&1; then
#        echo "E2E tests are configured"
#    else
#        echo "E2E tests not found, setting up..."
#        update_prow_share_context "tests.e2e.status" "not_started"
#    fi
#
#    # Or handle the error message directly:
#    e2e_status=$(get_prow_share_context_value "tests.e2e.status" 2>/dev/null)
#    if [[ -z "$e2e_status" ]]; then
#        echo "E2E status not set yet"
#    else
#        echo "E2E status: $e2e_status"
#    fi
#
# 6. Merge another JSON file with the context:
#    # Create a separate config file with additional data:
#    echo '{"environment": {"cluster": "test-cluster", "region": "us-east-1"}}' > /tmp/env_config.json
#
#    # Merge it with existing context (input file takes precedence on conflicts):
#    merge_prow_share_context "/tmp/env_config.json"
#
#    # Now the context contains both original and merged data:
#    # Original: {"tests": {"unit": {"status": "passed"}}}
#    # After merge: {"tests": {"unit": {"status": "passed"}}, "environment": {"cluster": "test-cluster", "region": "us-east-1"}}
#
# 7. View the complete context after updates:
#    get_prow_share_context
#    # Output example:
#    # {
#    #   "deployment": {
#    #     "ocp": {
#    #       "version": "4.15"
#    #     }
#    #   },
#    #   "tests": {
#    #     "unit": {
#    #       "status": "passed",
#    #       "count": "25"
#    #     },
#    #     "integration": {
#    #       "status": "running"
#    #     },
#    #     "e2e": {
#    #       "status": "not_started"
#    #     }
#    #   },
#    #   "environment": {
#    #     "cluster": {
#    #       "name": "test-cluster-01"
#    #     }
#    #   }
#    # }
#
# 7. Practical CI/CD workflow example:
#    # Step 1: Initialize test run
#    update_prow_share_context "run.id" "$(date +%s)"
#    update_prow_share_context "run.status" "started"
#
#    # Step 2: Record deployment info
#    update_prow_share_context "deployment.timestamp" "$(date -Iseconds)"
#    update_prow_share_context "deployment.commit_sha" "$GIT_COMMIT"
#
#    # Step 2.5: Merge external configuration if available
#    if [[ -f "$SHARED_DIR/cluster_config.json" ]]; then
#        merge_prow_share_context "$SHARED_DIR/cluster_config.json"
#    fi
#
#    # Step 3: During tests, update results
#    update_prow_share_context "tests.unit.passed" "23"
#    update_prow_share_context "tests.unit.failed" "2"
#
#    # Step 4: In later steps, read previous results
#    failed_count=$(get_prow_share_context_value "tests.unit.failed")
#    if [[ "$failed_count" -gt "0" ]]; then
#        echo "Unit tests failed: $failed_count failures"
#        update_prow_share_context "run.status" "failed"
#    fi

# Set default environment variable
: "${PROW_SHARE_CTX_FILE:=${SHARED_DIR}/prow_share_context.json}"

# Check for jq dependency upon sourcing
_check_jq_dependency() {
    if ! command -v jq >/dev/null 2>&1; then
        echo "Warning: jq tool not found. Attempting to install via pip3..."

        if command -v pip3 >/dev/null 2>&1; then
            if pip3 install jq >/dev/null 2>&1; then
                echo "Successfully installed jq via pip3"
            else
                echo "Error: Failed to install jq via pip3. Please install jq manually."
                echo "jq is required for prow_share_context.sh functionality."
                return 1
            fi
        else
            echo "Error: pip3 not available. Cannot install jq automatically."
            echo "Please install jq manually. jq is required for prow_share_context.sh functionality."
            return 1
        fi
    fi
    return 0
}

# Helper function to ensure context file exists and is initialized
_ensure_context_file() {
    # Check if context file exists
    if [[ ! -f "$PROW_SHARE_CTX_FILE" ]]; then
        # Create directory if it doesn't exist
        local context_dir
        context_dir=$(dirname "$PROW_SHARE_CTX_FILE")
        if [[ ! -d "$context_dir" ]]; then
            mkdir -p "$context_dir"
        fi

        # Create empty JSON object
        echo '{}' > "$PROW_SHARE_CTX_FILE"
    fi

    # Validate JSON format
    if ! jq . "$PROW_SHARE_CTX_FILE" >/dev/null 2>&1; then
        echo "Error: Invalid JSON in context file: $PROW_SHARE_CTX_FILE" >&2
        return 1
    fi

    return 0
}

# Function to get/initialize context
get_prow_share_context() {
    # Warn if parameters are passed (but still continue and return whole context)
    if [[ $# -gt 0 ]]; then
        echo "Warning: get_prow_share_context() does not expect parameters. Use get_prow_share_context_value(key) to get a specific value." >&2
        echo "Returning whole context instead..." >&2
    fi

    # Ensure context file exists and is valid (creates {} if not present)
    _ensure_context_file || return 1

    # Return the current context
    cat "$PROW_SHARE_CTX_FILE"
}

# Helper function to parse key path and convert to jq path array format
_parse_key_path() {
    local key="$1"

    if [[ -z "$key" ]]; then
        echo "Error: Key parameter is required" >&2
        return 1
    fi

    # Split the key by dots to create a JSON path array for nested access
    local path_parts
    IFS='.' read -ra path_parts <<< "$key"

    # Build jq path array string
    local jq_path="["
    local first=true
    for part in "${path_parts[@]}"; do
        if [[ "$first" == true ]]; then
            first=false
        else
            jq_path+=","
        fi
        jq_path+="\"$part\""
    done
    jq_path+="]"

    echo "$jq_path"
    return 0
}

# Function to get a value from context by key path
get_prow_share_context_value() {
    # Validate that exactly one parameter (key) is provided
    if [[ $# -eq 0 ]]; then
        echo "Error: get_prow_share_context_value() requires a key parameter" >&2
        echo "Usage: get_prow_share_context_value \"path.to.key\"" >&2
        return 1
    elif [[ $# -gt 1 ]]; then
        echo "Error: get_prow_share_context_value() expects only one parameter (key)" >&2
        echo "Usage: get_prow_share_context_value \"path.to.key\"" >&2
        return 1
    fi

    local key="$1"

    if [[ -z "$key" ]]; then
        echo "Error: Key parameter cannot be empty" >&2
        return 1
    fi

    # Ensure context file exists first (creates {} if not present)
    _ensure_context_file || return 1

    # Parse key path using helper function
    local jq_path
    jq_path=$(_parse_key_path "$key") || return 1

    # Extract value using jq getpath function
    local result
    result=$(jq -r "getpath($jq_path) // empty" "$PROW_SHARE_CTX_FILE" 2>/dev/null)

    # Check if the path exists (getpath returns null for non-existent paths)
    if [[ -z "$result" ]]; then
        # Check if path actually exists but has null/empty value
        if jq -e "has($(echo "$jq_path" | jq -r '.[0]'))" "$PROW_SHARE_CTX_FILE" >/dev/null 2>&1; then
            # Path exists but may be null/empty - check deeper
            if jq -e "getpath($jq_path) != null" "$PROW_SHARE_CTX_FILE" >/dev/null 2>&1; then
                echo "$result"
                return 0
            fi
        fi
        # Path doesn't exist - output error message and return nothing
        echo "Error: Key '$key' not found in context" >&2
        return 1
    fi

    echo "$result"
    return 0
}

# Function to merge another JSON file with the context file
# This function performs a deep merge of two JSON objects, with the input file
# taking precedence over existing values in case of conflicts
merge_prow_share_context() {
    local input_file="$1"

    # Validate that exactly one parameter (input file path) is provided
    if [[ $# -eq 0 ]]; then
        echo "Error: merge_prow_share_context() requires an input file parameter" >&2
        echo "Usage: merge_prow_share_context \"/path/to/input.json\"" >&2
        return 1
    elif [[ $# -gt 1 ]]; then
        echo "Error: merge_prow_share_context() expects only one parameter (input file path)" >&2
        echo "Usage: merge_prow_share_context \"/path/to/input.json\"" >&2
        return 1
    fi

    if [[ -z "$input_file" ]]; then
        echo "Error: Input file parameter cannot be empty" >&2
        return 1
    fi

    # Check if input file exists
    if [[ ! -f "$input_file" ]]; then
        echo "Error: Input file does not exist: $input_file" >&2
        return 1
    fi

    # Validate input file is valid JSON
    if ! jq . "$input_file" >/dev/null 2>&1; then
        echo "Error: Input file is not valid JSON: $input_file" >&2
        return 1
    fi

    # Ensure context file exists first (creates {} if not present)
    _ensure_context_file || return 1

    # Perform merge operation: existing context + input file (input takes precedence)
    # Uses jq's merge operator (*) for deep merge
    local temp_file
    temp_file=$(mktemp)

    if ! jq -s '.[0] * .[1]' "$PROW_SHARE_CTX_FILE" "$input_file" >| "$temp_file"; then
        echo "Error: Failed to merge JSON files" >&2
        rm -f "$temp_file"
        return 1
    fi

    # Atomically replace original file with merged content
    if ! mv -f "$temp_file" "$PROW_SHARE_CTX_FILE"; then
        echo "Error: Failed to save merged context file" >&2
        rm -f "$temp_file"
        return 1
    fi

    return 0
}

# Function to update context with a key-value pair using merge/patch semantics
# This function merges the new value at the specified path with existing JSON data,
# preserving all other existing fields and only updating the target path
update_prow_share_context() {
    local key="$1"
    local value="$2"

    if [[ -z "$key" ]]; then
        echo "Error: Key parameter is required" >&2
        return 1
    fi

    if [[ -z "$value" ]]; then
        echo "Error: Value parameter is required" >&2
        return 1
    fi

    # Ensure context file exists first (creates {} if not present)
    _ensure_context_file || return 1

    # Parse key path using shared helper function
    local jq_path
    jq_path=$(_parse_key_path "$key") || return 1

    # Perform merge/patch operation: read existing JSON, update only the specified path,
    # preserve all other existing data using jq's setpath function
    local temp_file
    temp_file=$(mktemp)

    if ! jq --arg value "$value" "setpath($jq_path; \$value)" "$PROW_SHARE_CTX_FILE" >| "$temp_file"; then
        echo "Error: Failed to merge/patch context file" >&2
        rm -f "$temp_file"
        return 1
    fi

    # Atomically replace original file with merged content
    if ! mv -f "$temp_file" "$PROW_SHARE_CTX_FILE"; then
        echo "Error: Failed to save merged context file" >&2
        rm -f "$temp_file"
        return 1
    fi

    return 0
}

# Check jq dependency when script is sourced
_check_jq_dependency