#!/bin/bash
set -euo pipefail

ACQUIRE_SCRIPT="$1"
RELEASE_SCRIPT="$2"
OUTPUT_FILE="$3"

UUID=$("${ACQUIRE_SCRIPT}")

for (( i=0; i<${#UUID}; i++ )); do
    printf '%s' "${UUID:$i:1}" >> "${OUTPUT_FILE}"
    sleep 0.05
done
printf '\n' >> "${OUTPUT_FILE}"

"${RELEASE_SCRIPT}" "${UUID}"
