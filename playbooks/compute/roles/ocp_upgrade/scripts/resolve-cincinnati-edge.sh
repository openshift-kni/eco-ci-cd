#!/bin/bash
# Compatibility entry point for callers that invoke this script with bash.
# OCP_UPGRADE_GRAPH_V1
exec python3 "$(dirname -- "${BASH_SOURCE[0]}")/resolve-cincinnati-edge.py" "$@"
