#!/usr/bin/env bash

REMOTE_NAME="${1:-"origin"}"
GIT_URL="${2:-"$(git config --get "remote.${REMOTE_NAME}.url" || true)"}"

function normalize_git_url() {
    local \
        url \
        result
    url="${1?cannot continue without url}"
    result="${url}"
    if [[ "${url}" == git@* ]]; then
        result="${url#git@}"
        result="${result/:/\/}"
        result="https://${result}"
    fi
    result="${result%.git}"
    echo "${result}"
    return 0
}

normalize_git_url "${GIT_URL}"
