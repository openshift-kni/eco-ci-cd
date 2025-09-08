#!/usr/bin/env bash
GIT_WEB_URL="${GIT_WEB_URL:-"https://raw.githubusercontent.com"}"
if [[ -z "${CURR_REPO}" ]]; then
	CURR_REPO="$(git config get remote.origin.url || true)"
	if [[ "${CURR_REPO}" == ^http* ]]; then
		CURR_REPO="${CURR_REPO##*//}" # rm http|s://
		CURR_REPO="${CURR_REPO##*/}"  # rm server name and path
	else
		CURR_REPO="${CURR_REPO##*:}"
	fi
	CURR_REPO="${CURR_REPO//.git/}"
fi
echo "detected current repo: ${CURR_REPO}"
if [[ -z "${CURR_BRANCH}" ]]; then
	CURR_BRANCH="$(git rev-parse --abbrev-ref HEAD || true)"
fi
echo "detected current branch: ${CURR_BRANCH}"
DIFF_TOOL="${DIFF_TOOL:-"vimdiff"}"
CLEANUP=()

function cleanup() {
	for f in "${CLEANUP[@]}"; do
		rm -f "${f}"
		echo "cleaned up ${f}"
	done
}

trap 'cleanup' EXIT

function github_diff() {
	local dst_file="${1:-"hack/rules/openshift_kni.py"}"
	local dst_branch="${2:-"${CURR_BRANCH}"}"
	local dst_repo="${3:-"${CURR_REPO}"}"
	local src_file="${4:-"hack/rules/redhat_ci.py"}"
	local src_branch="${5:-"main"}"
	local src_repo="${6:-"redhatci/ansible-collection-redhatci-ocp"}"

	LEFT="$(mktemp || true)"
	CLEANUP+=("${LEFT}")
	RIGHT="$(mktemp || true)"
	CLEANUP+=("${RIGHT}")

	echo "LEFT: ${LEFT}, RIGHT: ${RIGHT}"
	(curl -s "${GIT_WEB_URL}/${src_repo}/${src_branch}/${src_file}" || true) >"${LEFT}"
	(curl -s "${GIT_WEB_URL}/${dst_repo}/${dst_branch}/${dst_file}" || true) >"${RIGHT}"
	${DIFF_TOOL} "${LEFT}" "${RIGHT}"
	echo "after ${DIFF_TOOL}"
}

github_diff "${@}"
exit $?

# Usage examples
# ./hack/rules/diff_src.sh "path/to/file2" "main" "org2/repo2" "path/to/file1" "main" "org1/repo1"
# use nvim as diff tool
# DIFF_TOOL="nvim -d" ./hack/rules/diff_src.sh ...
# use beyond compare as diff tool:
# DIFF_TOOL="bcomp" ./hack/rules/diff_src.sh ...
