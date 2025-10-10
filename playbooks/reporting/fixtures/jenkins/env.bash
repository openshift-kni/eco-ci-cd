#!/bin/bash
# A realistic set of environment variables for a Jenkins pipeline job.
#
# SCENARIO:
# This script simulates the environment for a multibranch pipeline.
# It can be controlled to simulate a build from either GitLab or GitHub.

declare -a SCM_TYPES_SUPPORTED

SCM_TYPES_SUPPORTED+=("github")
SCM_TYPES_SUPPORTED+=("gitlab")
# TODO: add gerrit SCM_TYPES_SUPPORTED+=("gerrit")

function urldecode() {
  local url_encoded="${1//+/ }"
  printf '%b' "${url_encoded//%/\\x}"
}
#############################
# --- CONTROL VARIABLE --- #
#############################
# Set this to "gitlab" or "github" to control which set of SCM variables are defined.
export SCM_TYPE="${SCM_TYPE:-"github"}"

#########################################
# Jenkins Instance & Node Configuration #
#########################################

# The base URL of the Jenkins master instance.
export JENKINS_URL="https://ci.telco-v10n.fake.redhat.com"

# The path to the Jenkins home directory on the master.
export JENKINS_HOME="/var/lib/jenkins"

# The labels of the specific build agent (node) that picked up this job.
export NODE_LABELS="os:linux arch:amd64 arch:x86_64 containers:podman"

# The name of the build agent executing the job.
export NODE_NAME="build-agent-linux-05"

# The specific executor number on the agent (e.g., if the agent can run 4 jobs, this is 0, 1, 2, or 3).
export EXECUTOR_NUMBER="2"

############################
# Build/Job/Pipeline Details #
############################

# The name of the job. In a multibranch pipeline, this includes the branch name.
# Jenkins often sanitizes the branch name, replacing '/' with '%2F'.
export JOB_NAME="cnf-run-kuku-ruku_ocp-4.18/feature%2Fnew-ui-component"

# The full URL to the job's main page.
# DERIVATION: ${JENKINS_URL}/job/${JOB_NAME}/
export JOB_URL="${JENKINS_URL}/job/cnf-run-kuku-ruku_ocp-4.18/job/feature%2Fnew-ui-component/"

# The unique identifier for this specific build run. Usually the same as BUILD_NUMBER.
export BUILD_ID="152"

# The incrementing number for this specific build of this job/branch.
export BUILD_NUMBER="152"

# A unique string that identifies this build, often used for artifact tagging.
# DERIVATION: jenkins-${JOB_NAME}-${BUILD_NUMBER} (with sanitized JOB_NAME)
export BUILD_TAG="jenkins-cnf-run-kuku-ruku_ocp-4.18-feature_new-ui-component-152"

# The full URL to this specific build's console output, artifacts, etc.
# DERIVATION: ${JOB_URL}${BUILD_NUMBER}/
export BUILD_URL="${JOB_URL}${BUILD_NUMBER}/"

# The cause of the build.
export BUILD_CAUSE="USERIDCAUSE,SCMTRIGGER"

# The absolute path on the build agent where the work is being done.
# DERIVATION: For multibranch pipelines, it's often ${JENKINS_HOME}/workspace/${JOB_NAME}
export WORKSPACE="${JENKINS_HOME}/workspace/cnf-run-kuku-ruku_ocp-4.18_feature_new-ui-component"


###################################
# Source Control & Change Details #
###################################

# --- Generic Git Details (common to both SCMs) ---
# In a multibranch pipeline, this is the name of the branch being built.
GIT_BRANCH="$(urldecode "${JOB_NAME##*/}")"
export GIT_BRANCH
GIT_LOCAL_BRANCH="$(urldecode "${JOB_NAME##*/}")"
export GIT_LOCAL_BRANCH

# The commit hash that triggered this build.
export GIT_COMMIT="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"

# Committer details from the git log.
export GIT_COMMITTER_NAME="Zeezee Tryppo"
export GIT_COMMITTER_EMAIL="ztrypo@unreal.redhat.com"

# The commit hash of the previous build (can be any branch).
export GIT_PREVIOUS_COMMIT="f0e9d8c7b6a5f0e9d8c7b6a5f0e9d8c7b6a5f0e9d8c7"

# The commit hash of the last *successful* build of this branch.
export GIT_PREVIOUS_SUCCESSFUL_COMMIT="f0e9d8c7b6a5f0e9d8c7b6a5f0e9d8c7b6a5f0e9d8c7"

# --- Platform-Specific SCM Details ---

case "${SCM_TYPE}" in 
    "gitlab")
        echo "INFO: Defining Jenkins ${SCM_TYPE}-specific environment variables."
        export GIT_URL="https://gitlab.cee.redhat.com/acme-corp/telco/cnf-testing.git"

        # -- GitLab Merge Request Details --
        export GITLAB_MERGE_REQUEST_IID="42"
        export GITLAB_MERGE_REQUEST_LAST_COMMIT_SHA="${GIT_COMMIT}"
        export GITLAB_MERGE_REQUEST_SOURCE_BRANCH="${GIT_BRANCH}"
        export GITLAB_MERGE_REQUEST_TARGET_BRANCH="main"
        export GITLAB_USER_NAME="Sergio Constanza"
        export GITLAB_USER_EMAIL="sergioc@telcov10n.redhat.com"

        # -- Generic CHANGE_* variables populated by the GitLab plugin --
        export CHANGE_ID="${GITLAB_MERGE_REQUEST_IID}"
        export CHANGE_BRANCH="${GITLAB_MERGE_REQUEST_SOURCE_BRANCH}"
        export CHANGE_TARGET="${GITLAB_MERGE_REQUEST_TARGET_BRANCH}"
        export CHANGE_AUTHOR="sergioc"
        export CHANGE_AUTHOR_DISPLAY_NAME="${GITLAB_USER_NAME}"
        export CHANGE_URL="https://gitlab.com/acme-corp/telco/cnf-testing/-/merge_requests/${CHANGE_ID}"
        export CHANGE_FORK="" # Populated if the MR comes from a fork.
    ;;
    "github")
        echo "INFO: Defining Jenkins ${SCM_TYPE}-specific environment variables."
        export GIT_URL="https://github.com/acme-corp/cnf-testing.git"

        # -- GitHub Pull Request Details --
        # Note: PULL_REQUEST_* variables are from older plugins. Newer ones use CHANGE_*.
        # We include both for broader compatibility testing.
        export GITHUB_PR_NUMBER="87"
        export PULL_REQUEST_ID="${GITHUB_PR_NUMBER}"

        # -- Generic CHANGE_* variables populated by the GitHub plugin --
        export CHANGE_ID="${GITHUB_PR_NUMBER}"
        export CHANGE_BRANCH="${GIT_BRANCH}" # Source branch
        export CHANGE_TARGET="main" # Base branch
        export CHANGE_AUTHOR="sergioc"
        export CHANGE_AUTHOR_DISPLAY_NAME="Sergio Constanza"
        export CHANGE_URL="https://github.com/acme-corp/cnf-testing/pull/${CHANGE_ID}"
        export CHANGE_FORK="" # Populated if the PR comes from a fork.
    ;;
    *)
        echo "Unsupported SCM_TYPE: ${SCM_TYPE}"
        echo "Only these are currently supported:"
        for item in "${SCM_TYPES_SUPPORTED[@]}"; do echo -e "\t'${item}'"; done
        exit 1;
    ;;
esac