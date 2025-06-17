#!/usr/bin/env bash
# shellcheck disable=SC2065
###############################################################################
# Make targets logic in shell
###############################################################################
# TODO: migrate this code into python
set -o pipefail
SCRIPT_DBG="${SCRIPT_DBG:-0}"
# whether we shall not send data and set specific CI
DEV_MODE="${DEV_MODE:-0}"
# do not recreate by default
RECREATE="${RECREATE:-0}"
# use the default python3.
PY="${PY:-"python3"}"
# where to install current venv directory
VENV_DIR="${VENV_DIR:-"${PWD}/.venv"}"
# ansible vars/ directory
VARS_DIR="${VARS_DIR:-"${PWD}/vars"}"
# jinja data file path
OUT_DIR="${OUT_DIR:-"${PWD}/output"}"
# jinja templates directory
TPL_DIR="${TPL_DIR:-"${PWD}/templates"}"
# jinja intermediate data file
DATA_FILE="${DATA_FILE:-"${OUT_DIR}/data.yml"}"
# ansible playbook file
PLAYBOOK="${PLAYBOOK:-"test_report_send.yml"}"
# extra data generator script
GENERATOR="${GENERATOR:-"tools/gen_playbook_extra_vars.py"}"
# extra data file template
TPL_FILE="${TPL_FILE:-"${TPL_DIR}/${PLAYBOOK##*/}.j2"}"
# extra vars for the playbook
EXTRA_VARS="${EXTRA_VARS:-"${VARS_DIR}/${PLAYBOOK##*/}"}"
ANSIBLE_COLLECTIONS_PATH="${ANSIBLE_COLLECTIONS_PATH:-"${PWD}/collections"}"
CACHE_PATH="${CACHE_PATH:-"${PWD}/.ansible"}"
TEST="${TEST:-"dci"}"
COLLECTION_ROOT="${COLLECTION_ROOT:-""}"
COLLECTIONS_REQS_LOCAL="${COLLECTIONS_REQS_LOCAL:-"requirements.local.yml"}"
COLLECTION_REQ_FILES_TXT="${COLLECTION_REQ_FILES_TXT:-"requirements.yml"}"
FIXTURES_ROOT="${FIXTURES_ROOT:-"fixtures"}"
TEST_DATA_DIR="${TEST_DATA_DIR:-"${FIXTURES_ROOT}/${TEST}"}"
REQ_COLLECTIONS_ATTR="${REQ_COLLECTIONS_ATTR:-"collections"}"
YQ_SEARCH_PREFIX="${YQ_SEARCH_PREFIX:-".${REQ_COLLECTIONS_ATTR}[]"}"
# this option affects die function behavior
LIVE_FOREVER="${LIVE_FOREVER:-"0"}"

if ! declare -p EXTRA_PARAMS 2>/dev/null | grep -q '^declare -a'; then
  # declare it if it isn't defined yet
  declare -a EXTRA_PARAMS
fi
if [[ "${#EXTRA_PARAMS[@]}" -eq 0 ]]; then
  # at least set it to this:
  EXTRA_PARAMS+=("-vv")
fi

declare -a SUPPORTED_ACTIONS
SUPPORTED_ACTIONS=(
  bootstrap
  gendata
  buildpkg
  render
  run_playbook
  test
)

function help() {
  local \
    item \
    action
  action="${1}"
  echo -e "ERROR: Unsupported action: '${action}'"
  echo -e "\tSupported actions:"
  for item in "${SUPPORTED_ACTIONS[@]}"; do
    echo -e "\t'${item}'"
  done
  echo -e "\t=>\tPlease re-run using a supported action"
}

function log.msg() {
  local \
    level \
    ts
  local -a msg
  level="${1?cannot continue without level}"
  level="${level^^}"
  shift 1
  msg=("${@}")
  if [[ "${level}" = "DEBUG" && "${SCRIPT_DBG}" -eq 0 ]]; then
    return 0
  fi
  ts="$(date -u || true)"
  echo -e -n "${ts} - ${level} - ${msg[*]}\n"
  return 0
}

function log.info() {
  local level="${FUNCNAME[0]}"
  local -a msg=("${@}")
  log.msg "${level##*.}" "${msg[@]}"
  return $?
}

function log.error() {
  local level="${FUNCNAME[0]}"
  local -a msg=("${@}")
  log.msg "${level##*.}" "${msg[@]}"
  return $?
}

function log.fatal() {
  local level="${FUNCNAME[0]}"
  local -a msg=("${@}")
  log.msg "${level##*.}" "${msg[@]}"
  return $?
}

function log.warn() {
  local op="${FUNCNAME[0]}"
  local -a msg=("${@}")
  log.msg "${op##*.}" "${msg[@]}"
  return $?
}

function log.debug() {
  local level="${FUNCNAME[0]}"
  local -a msg=("${@}")
  log.msg "${level##*.}" "${msg[@]}"
  return $?
}

function die() {
  ####################################################################################################################
  # die prints the message and exits with rc
  # if LIVE_FOREVER is non 0, it returns.
  ####################################################################################################################
  local rc msg
  rc="${1?cannot without rc}"
  shift 1
  msg="${*}"
  log.fatal "${msg}"
  if [[ "${LIVE_FOREVER}" -ne 0 ]]; then
    return "${rc}"
  fi
  exit "${rc}"
}

function prolog() {
  ####################################################################################################################
  # prolog prints the name of the caller function and passed arguments
  # it should be called by callers as the FIRST command of a function like this: prolog "${@}"
  ####################################################################################################################
  local \
    func_name \
    msg \
    item
  local -a vars
  func_name="${FUNCNAME[1]}"
  log.debug "Inside ${func_name}()\n"
  log.debug "The call (debug) was: '${FUNCNAME[1]} ${*}'\n"
  return 0
}

function epilog() {
  ####################################################################################################################
  # epilog prints the name of the caller function and how it returned
  # it should be called by callers as the LAST command of a function like this: epilog "${@}"
  ####################################################################################################################

  local \
    name \
    rc
  local -a msg
  name="${FUNCNAME[1]}"
  rc="${1?cannot continue without rc}"
  shift 1
  msg=("Function ${name}()")
  msg+=("${@}")
  msg+=("completed with rc=${rc}")
  log.debug "${msg[@]}"
}

function run_cmd() {
  local -a \
    cmd
  local \
    expected_rc \
    rc
  prolog "${@}"
  expected_rc="${1?cannot continue without expected_rc}"
  shift 1
  cmd=("${@}")
  test "${#cmd[@]}" -ne 0 || die 1 "The command '${cmd[*]}' cannot be empty"
  log.debug "About to run command: '${cmd[*]}'"
  "${cmd[@]}"
  rc=$?
  test "${rc}" -eq "${expected_rc}" || die "${rc}" "The command returned unexpected rc=${rc}. [EXPECTED: ${expected_rc}]"
  epilog "${rc}"
  return "${rc}"
}

function is_in_venv() {
  local \
    venv_dir \
    py_exec \
    curr_py \
    venv_py \
    out
  venv_dir="${1?cannot continue without venv_dir}"
  py_exec="${2:-"${PY}"}"
  curr_py="$(command -v "${py_exec}" 2>/dev/null || true)"
  venv_py="$(realpath "${venv_dir}/bin/${py_exec}" || true)"
  out="true"
  if [[ "${venv_py}" != "${curr_py}" ]]; then
    out="false"
  fi
  echo "${out}"
  return 0

}

function source_script() {
  local \
    script_path \
    subdir \
    rc
  local -a \
    path_to_script
  script_path="${1?cannot continue without script_path}"

  path_to_script=("$(dirname "${script_path}" || true)")
  path_to_script=("$(dirname "${path_to_script[0]}" || true)" "${path_to_script[@]}")
  path_to_script=("$(dirname "${path_to_script[0]}" || true)" "${path_to_script[@]}")

  # validations: dirs presence + permissions
  for subdir in "${path_to_script[@]}"; do
    test -d "${subdir}" || die 1 "'${subdir}' folder is missing"
    test -x "${subdir}" || die 1 "'${subdir}' folder is non executable"
  done
  # validations: script permissions
  test -r "${script_path}" || die 1 "Expected script file ${script_path} is not readable."
  # shellcheck disable=SC1090
  source "${script_path}"
  rc=$?
  log.debug "sourced ${script_path} with rc=${rc}"
  test "${rc}" -eq 0 || die "${rc}" "Failed on ${script_path} sourcing. Please check your environment."
  return "${rc}"
}

function venv_activate() {
  local \
    venv_dir \
    py_exec \
    subdir \
    expected_rc \
    rc
  prolog "${@}"
  venv_dir="${1?cannot continue without venv_dir}"
  py_exec="${2:-"${PY}"}"
  expected_rc=0
  venv_enabled="$(is_in_venv "${venv_dir}" "${py_exec}" || true)"
  if [[ "${venv_enabled}" = "true" ]]; then
    log.warn "venv ${venv_dir} is currently active"
    return 0
  fi
  log.info "Activating venv in ${venv_dir}"
  source_script "${venv_dir}/bin/activate"
  rc=$?
  test "${rc}" -eq "${expected_rc}" || die "${rc}" "Activating venv '${venv_dir}' returned rc=${rc} [EXPECTED: ${expected_rc}]"
  epilog "${rc}"
  return "${rc}"
}

function install_collection_from_yml() {
  local \
    requirement \
    collections_path \
    rc
  local -a \
    curr_cmd
  prolog "${@}"
  requirement="${1?cannot continue without requirement}"
  collections_path="${2:-"${ANSIBLE_COLLECTIONS_PATH}"}"
  # take the 1st item if it has multiple items separated by :
  collections_path="${collections_path%%:*}"
  curr_cmd=(ansible-galaxy collection install --force -r "${requirement}" -p "${collections_path}")
  run_cmd 0 "${curr_cmd[@]}"
  rc=$?
  epilog "${rc}" "Collection installed from: '${requirement}'"
  return "${rc}"
}

function install_collection_pkg() {
  local \
    count \
    requirement \
    yq_search_term \
    item \
    package \
    collections_path \
    rc
  local -a \
    curr_cmd
  prolog "${@}"
  requirement="${1?cannot continue without requirement}"
  collections_path="${2:-"${ANSIBLE_COLLECTIONS_PATH}"}"
  # take the 1st item if it has multiple items separated by :
  collections_path="${collections_path%%:*}"
  yq_search_term="${3:-"${YQ_SEARCH_PREFIX}.source"}"
  # install packages
  log.debug "Processing requirements file: '${requirement}'"
  curr_cmd=(yq -r "${yq_search_term}" "${requirement}")
  run_cmd 0 "${curr_cmd[@]}" >/dev/null
  rc=$?
  # log.debug ">>>>\tLook above  ^^^, current command: '${curr_cmd[*]}', returned rc=${rc}"
  count=0
  while [[ "${rc}" -eq 0 ]] && read -r package; do
    package="${package//file:\/\//}"
    if ! [[ -r "${package}" ]]; then
      log.debug "Processing: '${item}'. Skipped installing missing package: ${package}"
      continue 1
    fi
    log.info "Installing collection from package: ${package}"
    run_cmd 0 ansible-galaxy collection install --force "${package}" -p "${collections_path}"
    rc=$?
    log.info "==> Installed collection from: ${package} with rc=${rc}"
    count=$((count + 1))
  done < <("${curr_cmd[@]}" || true)
  log.info "Installed: ${count} collections"
}

function install_collection_py_reqs() {
  local \
    count \
    requirement \
    yq_search_term \
    py_req_file_path \
    py_req \
    package \
    collection \
    collections_path \
    rc
  local -a \
    curr_cmd
  prolog "${@}"
  requirement="${1?cannot continue without requirement}"
  collections_path="${2:-"${ANSIBLE_COLLECTIONS_PATH}"}"
  # take the 1st item if it has multiple items separated by :
  collections_path="${collections_path%%:*}"
  yq_search_term="${3:-"${YQ_SEARCH_PREFIX}.name"}"
  py_req="${4:-"requirements.txt"}"
  curr_cmd=(yq -r "${yq_search_term}" "${requirement}")
  run_cmd 0 "${curr_cmd[@]}"
  rc=$?
  count=0
  log.info "Installing python requirements for collections from requirements yaml file: ${requirement}"
  while read -r collection; do
    py_req_file_path="${collections_path}/ansible_collections/${collection//\./\/}/meta/${py_req}"
    if ! [[ -r "${py_req_file_path}" ]]; then
      log.warn "The collection '${collection}' python requirements file '${py_req_file_path}' is unreadable"
      continue 1
    fi
    log.debug "Found collection ${collection} python requirements: ${py_req_file_path}"
    run_cmd 0 pip3 install -r "${py_req_file_path}"
    rc=$?
    log.info "==> Installed python requirements: ${py_req_file_path} for collection ${collection} with rc=${rc}"
    count=$((count + 1))
  done < <("${curr_cmd[@]}" || true)
  log.info "Installed: ${count} python requirements files"
  return "${rc}"
}

function collections_install() {
  local \
    item \
    var \
    val \
    collections_path \
    idx \
    total \
    yq_search_prefix
  local -a \
    vars \
    requirements \
    curr_cmd
  prolog "${@}"
  collections_path="${1?cannot continue without collections_path}"
  vars+=(collections_path)
  shift 1
  for var in "${vars[@]}"; do
    val="$(eval "echo \$${var}" || true)"
    test -n "${val}" && log.debug "updated: ${var}='${val}'"
  done
  requirements=("${@}")
  if [[ "${#requirements[@]}" -eq 0 ]]; then
    requirements+=("requirements.yml")
    log.debug "Requirements are now: '${requirements[*]}'"
  fi
  # install from the 1st requirement:
  install_collection_from_yml \
    "${requirements[0]}" \
    "${collections_path}"
  rc=$?
  log.debug "Installed collections from ${requirements[0]} with rc=${rc}"
  # pop the 1st requirement from requirements:
  requirements=("${requirements[@]:1}")
  yq_search_prefix="${YQ_SEARCH_PREFIX}"
  idx=0
  total="${#requirements[@]}"
  # go over remainder:
  for item in "${requirements[@]}"; do
    log.info "==> Installing requirements ${item} [${idx}/${total}]"
    # install packages
    install_collection_pkg "${item}" "${collections_path}" "${yq_search_prefix}.source"
    rc=$?
    log.debug "Installed collection from ${item} to ${collections_path} with rc=${rc}"
    install_collection_py_reqs "${item}" "${collections_path}" "${yq_search_prefix}.name"
    rc=$?
    log.debug "Installed python requirements ${item} to ${collections_path} with rc=${rc}"
    idx=$((idx + 1))
  done
  test "${idx}" -eq 1 && val="" || val="s"
  epilog "${rc}" "passing ${idx} yaml requirements file${val}"
  return "${rc}"
}

function lazy_collections_install() {
  local \
    item \
    msg \
    collections_path \
    cache_path \
    recreate \
    var \
    val \
    rc
  local -a \
    reqs \
    vars
  prolog "${@}"
  collections_path="${1:-"${ANSIBLE_COLLECTIONS_PATH}"}"
  # take the 1st item if it has multiple items separated by :
  collections_path="${collections_path%%:*}"
  vars+=(collections_path)
  shift 1
  recreate="${1:-"${RECREATE}"}"
  vars+=(recreate)
  shift 1
  cache_path="${1:-"${CACHE_PATH}"}"
  vars+=(cache_path)
  shift 1
  reqs=("${@}")
  if [[ "${#reqs[@]}" -eq 0 ]]; then
    IFS=',' read -r -a reqs <<<"${COLLECTION_REQ_FILES_TXT}"
  fi
  for var in "${vars[@]}"; do
    val="$(eval "echo \$${var}" || true)"
    test -n "${val}" && log.debug "updated: ${var}='${val}'"
  done
  rc=0
  if [[ -d "${collections_path}" ]]; then
    if [[ "${recreate}" -eq 0 ]]; then
      log.warn "no need to clean up collections_path. [REASON: recreate=${recreate}]"
      return "${rc}"
    fi
    rm -fr "${collections_path}"
    log.info "deleted collections_path='${collections_path}'. [REASON: recreate=${recreate}]"
  fi
  if [[ -d "${cache_path}" ]]; then
    if [[ "${recreate}" -eq 0 ]]; then
      log.warn "no need to clean up cache_path. [REASON: recreate=${recreate}]"
      return "${rc}"
    fi
    rm -fr "${cache_path}"
    log.info "deleted cache_path='${cache_path}'. [REASON: recreate=${recreate}]"
  fi
  collections_install "${collections_path}" "${reqs[@]}"
  rc=$?
  test "${rc}" -eq 0 || die "${rc}" "Failed to install collections"
  epilog "${rc}"
  return "${rc}"
}

function venv_install() {
  local \
    msg \
    item \
    venv_dir \
    host_py \
    venv_py \
    rc
  local -a \
    requirements \
    vars \
    cmd
  prolog "${@}"
  venv_dir="${1?cannot continue without venv_dir}"
  vars+=(venv_dir)
  shift 1
  host_py="${1:-"${PY}"}"
  vars+=(host_py)
  shift 1
  requirements+=("${@}")

  for var in "${vars[@]}"; do
    val="$(eval "echo \$${var}" || true)"
    test -n "${val}" && log.debug "updated: ${var}='${val}'"
  done
  if [[ "${#requirements[@]}" -eq 0 ]]; then
    requirements+=("requirements.txt")
  fi
  log.debug "using requirements: ${requirements[*]}"
  venv_py="${host_py##*/}"
  log.debug "Installing venv at ${venv_dir}"
  cmd=("${host_py}" -m venv "${venv_dir}")
  run_cmd 0 "${cmd[@]}"
  rc=$?
  venv_activate "${venv_dir}" "${venv_py}"
  rc=$?
  log.info "==> Created venv of ${venv_py} in ${venv_dir} and activated it"
  cmd=("${venv_py}" -m pip install --upgrade pip)
  # save old value
  run_cmd 0 "${cmd[@]}"
  rc=$?
  log.info "==> Upgraded pip using venv python ${venv_py} with rc=${rc}"
  cmd=("${venv_py}" -m pip install)
  for item in "${requirements[@]}"; do
    cmd+=("-r" "${item}")
  done
  run_cmd 0 "${cmd[@]}"
  rc=$?
  log.info "==> Installed venv packages from ${requirements[*]} with rc=${rc}"
  log.info "==> Version info on python interpreter: $("${venv_py}" --version || true)"
  return 0
}

function lazy_venv_install() {
  local \
    msg \
    item \
    venv_dir \
    collections_path \
    recreate \
    var \
    val \
    rc
  local -a \
    vars
  prolog "${@}"
  venv_dir="${1:-"${VENV_DIR}"}"
  vars+=(venv_dir)
  shift 1
  py="${1:-"${PY}"}"
  vars+=(py)
  shift 1
  recreate="${1:-"${RECREATE}"}"
  vars+=(recreate)
  shift 1
  for var in "${vars[@]}"; do
    val="$(eval "echo \$${var}" || true)"
    test -n "${val}" && log.debug "updated: ${var}='${val}'"
  done
  rc=0
  if [[ -d "${venv_dir}" ]]; then
    if [[ "${recreate}" -eq 0 ]]; then
      log.warn "no need to install venv. [REASON: recreate=${recreate}]"
      return "${rc}"
    fi
  fi
  if [[ "${recreate}" -gt 0 ]]; then
    rm -fr "${venv_dir}"
    log.info "deleted ${venv_dir}. [REASON: recreate=${recreate}]"
  fi
  venv_install "${venv_dir}" "${py}"
  rc=$?
  return "${rc}"
}

function action.bootstrap() {
  local \
    msg \
    item \
    venv_dir \
    py \
    collections_path \
    cache_path \
    recreate \
    val \
    var \
    rc
  local -a \
    vars \
    reqs
  prolog "${@}"
  venv_dir="${1:-"${VENV_DIR}"}"
  vars+=(venv_dir)
  shift 1
  py="${1:-"${PY}"}"
  vars+=(py)
  shift 1
  collections_path="${1:-"${ANSIBLE_COLLECTIONS_PATH}"}"
  # take the 1st item if it has multiple items separated by :
  collections_path="${collections_path%%:*}"
  vars+=(collections_path)
  shift 1
  recreate="${1:-"${RECREATE}"}"
  vars+=(recreate)
  shift 1
  cache_path="${1:-"${CACHE_PATH}"}"
  vars+=(cache_path)
  shift 1
  for var in "${vars[@]}"; do
    val="$(eval "echo \$${var}" || true)"
    test -n "${val}" && log.debug "updated: ${var}='${val}'"
  done
  reqs=("${@}")
  log.debug "=======> Accepted reqs: ${reqs[*]}"
  if [[ "${#reqs[@]}" -eq 0 ]]; then
    IFS=',' read -r -a reqs <<<"${COLLECTION_REQ_FILES_TXT}"
    log.debug "After adjusting reqs as it was empty"
  fi
  log.debug "=======> Adjusted reqs: ${reqs[*]}"
  lazy_venv_install "${venv_dir}" "${py}" "${recreate}"
  rc=$?
  log.debug "lazy_venv_install() returned rc=${rc}"
  if [[ "${DEV_MODE}" -gt 0 ]]; then
    if [[ "${#reqs[@]}" -eq 1 ]]; then
      reqs+=(requirements-dev.yml)
    fi
  fi
  lazy_collections_install "${collections_path}" "${recreate}" "${cache_path}" "${reqs[@]}"
  rc=$?

  log.debug "Outside ${FUNCNAME[0]}() returning rc=${rc}"
  return "${rc}"
}

function gendata() {
  local \
    msg \
    item \
    venv_dir \
    data \
    generator \
    var \
    val \
    rc
  local -a \
    vars \
    cmd
  prolog "${@}"
  venv_dir="${1:-"${VENV_DIR}"}"
  vars+=(venv_dir)
  shift 1
  data="${1:-"${DATA_FILE}"}"
  vars+=(data)
  shift 1
  generator="${1:-"${GENERATOR}"}"
  vars+=(generator)
  for var in "${vars[@]}"; do
    val="$(eval "echo \$${var}" || true)"
    test -n "${val}" && log.debug "updated: ${var}='${val}'"
  done
  cmd=("python3" "${generator}" "--outfile=${data}")
  if [[ "${DEV_MODE}" -gt 0 ]]; then

    vars=("--skip-send")
    cmd+=("${vars[@]}")
    log.warn "Updating the command with dev flags: ${vars[*]}"
  fi
  run_cmd 0 "${cmd[@]}"
  rc=$?
  epilog "${rc}"
  return "${rc}"
}

function print_debug_var_name() {
  local \
    var_name \
    var_value
  var_name="${1?cannot continue without var_name}"
  var_value="$(eval echo "\$${var_name}" || true)"
  log.info "variable ${var_name}='${var_value}'"
}

function print_test_type_detection_var() {
  local \
    test_type \
    var_name \
    var_value
  test_type="${1?cannot continue without test_type}"

  case "${test_type}" in
  "dci") var_name="DCI_CS_URL" ;;
  "jenkins") var_name="JENKINS_URL" ;;
  "github") var_name="GITHUB_API_URL" ;;
  "gitlab") var_name="GITLAB_CI" ;;
  "prow") var_name="PROW_JOB_ID" ;;
  *) die 1 "Bad name for test_type: ${test_type}" ;;
  esac
  log.info "test_type='${test_type}' ==> "
  print_debug_var_name "${var_name}"
}

function gen_local_reqs_yaml() {
  local \
    collection_pkg_path \
    reqs_local \
    reqs_local_backup \
    collection_name \
    rc
  prolog "${@}"
  collection_pkg_path="${1?cannot continue without collection_pkg_path}"
  shift 1
  reqs_local="${1:-"${COLLECTIONS_REQS_LOCAL}"}"
  shift 1
  collection_name="${1:-""}"
  if [[ -z "${collection_name}" ]]; then
    # take last path item: transform path/to/${ns}-${col}-${version}.tar.gz -> ${ns}-${col}-${version}.tar.gz
    collection_name="${pkg_path##*/}"
    # remove last -* component: transform ${ns}-${col}-${version}.tar.gz -> ${ns}-${col}
    collection_name="${collection_name%-*}"
    # replace '-' with '.'
    collection_name="${collection_name//-/.}"
  fi
  if [[ -r "${reqs_local}" ]]; then
    reqs_local_backup="backup.$(date +%s || true).${reqs_local}"
    cp -p "${reqs_local}" "${reqs_local_backup}"
    log.warn "Backed up pre-existing local requirements yaml (${reqs_local} ==> ${reqs_local_backup})"
  fi
  log.info "Creating ${reqs_local} file for collection: ${collection_name} at path: ${collection_pkg_path}"
  cat >"${reqs_local}" <<-_EOF_
	---
	collections:
	  - source: file://${collection_pkg_path}
	    name: ${collection_name}
	_EOF_
  rc=$?
  log.info "created up-to-date ${reqs_local} file."
  epilog "${rc}"
  return "${rc}"
}

function action.gendata() {
  local \
    msg \
    item \
    venv_dir \
    data \
    generator \
    recreate \
    var \
    val \
    rc
  local -a \
    vars

  prolog "${@}"
  venv_dir="${1:-"${VENV_DIR}"}"
  vars+=(venv_dir)
  shift 1
  data="${1:-"${DATA_FILE}"}"
  vars+=(data)
  shift 1
  generator="${1:-"${GENERATOR}"}"
  vars+=(generator)
  shift 1
  recreate="${1:-"${RECREATE}"}"
  vars+=(recreate)
  shift 1
  for var in "${vars[@]}"; do
    val="$(eval "echo \$${var}" || true)"
    test -n "${val}" && log.debug "updated: ${var}='${val}'"
  done
  if [[ -r "${data}" ]]; then
    if [[ "${recreate}" -eq 0 ]]; then
      log.debug "Skip data generation. [REASON: recreate=${recreate}]"
      return 0
    fi
  fi
  gendata "${venv_dir}" "${data}" "${generator}"
  rc=$?
  epilog "${rc}"
  return "${rc}"
}

function action.buildpkg() {
  local \
    venv_dir \
    recreate \
    collection_root \
    collections_path \
    reqs_local \
    item \
    rc
  local -a \
    vars
  prolog "${@}"
  venv_dir="${1?cannot continue without venv_dir}"
  vars+=(venv_dir)
  shift 1
  recreate="${1:-"${RECREATE}"}"
  vars+=(recreate)
  shift 1
  collection_root="${1:-"${COLLECTION_ROOT}"}"
  vars+=(collection_root)
  shift 1
  reqs_local="${1:-"${COLLECTIONS_REQS_LOCAL}"}"
  vars+=(reqs_local)
  shift 1
  for var in "${vars[@]}"; do
    val="$(eval "echo \$${var}" || true)"
    test -n "${val}" && log.debug "updated: ${var}='${val}'"
  done

  if [[ -z "${collection_root}" ]]; then
    log.warn "Skip installations. [REASON: collection root unset or missing]"
    return 0
  fi
  log.info "jumping into ${collection_root} folder"
  pushd "${PWD}" 2>/dev/null 1>/dev/null || die 1 "failed to pushd ${PWD}"
  cd "${collection_root}" || die 1 "failed to chdir to collection_root=${collection_root}"
  log.info "Rebuilding a collection at ${collection_root}"
  venv_activate "${venv_dir}"
  pkg_path="$(ansible-galaxy collection build --force || true)"
  # take the last word
  pkg_path="${pkg_path##* }"
  popd 2>/dev/null >/dev/null || die 1 "failed to popd"
  log.info "Isolated package path: ${pkg_path}"
  gen_local_reqs_yaml "${pkg_path}" "${reqs_local}"
  log.info "Created requirements file: ${reqs_local}"
  rc=$?
  epilog "${rc}" "installed the collection"
  return "${rc}"
}

function action.render() {
  local \
    msg \
    item \
    venv_dir \
    extra_var \
    playbook \
    data_file \
    tpl_file \
    output_file \
    msg \
    var \
    val \
    rc
  local -a \
    vars \
    cmd
  prolog "${@}"
  venv_dir="${1?cannot continue without venv_dir}"
  vars+=(venv_dir)
  shift 1
  data_file="${1:-"${DATA_FILE}"}"
  vars+=(data_file)
  shift 1
  playbook="${1:-"${PLAYBOOK}"}"
  vars+=(playbook)
  shift 1
  tpl_file="${1:-"${TPL_FILE}"}"
  vars+=(tpl_file)
  shift 1
  output_file="${1:-"${EXTRA_VARS}"}"
  vars+=(output_file)

  for var in "${vars[@]}"; do
    val="$(eval "echo \$${var}" || true)"
    test -n "${val}" && log.debug "updated: ${var}='${val}'"
  done
  venv_activate "${venv_dir}"
  cmd=(jinja "--format=yaml")
  cmd+=("--data=${data_file}")
  cmd+=("--output=${output_file}")
  cmd+=("${tpl_file}")
  run_cmd 0 "${cmd[@]}"
  rc=$?
  log.info "Extra variables file ${output_file} has been created successfully."
  log.info "Now you can invoke the playbook via make targets: 'run' or 'test_source'"
  epilog "${rc}"
  return "${rc}"
}

function action.run_playbook() {
  local \
    msg \
    item \
    extra_var \
    extra_param \
    venv_dir \
    playbook \
    extra_vars_txt \
    var \
    val \
    rc
  local -a \
    vars \
    extra_vars \
    extra_params \
    cmd
  prolog "${@}"
  venv_dir="${1:-"${VENV_DIR}"}"
  vars+=(venv_dir)
  shift 1
  playbook="${1:-"${PLAYBOOK}"}"
  vars+=(playbook)
  shift 1
  extra_vars_txt="${1:-""}"
  vars+=(extra_vars_txt)
  shift 1
  for var in "${vars[@]}"; do
    val="$(eval "echo \$${var}" || true)"
    test -n "${val}" && log.debug "updated: ${var}='${val}'"
  done
  extra_params=("${@}")
  if [[ "${#extra_params[@]}" -eq 0 ]]; then
    extra_params=("${EXTRA_PARAMS[@]}")
  fi
  if [[ "${#extra_params[@]}" -ne 0 ]]; then
    log.debug "updated: extra_params: ${extra_params[*]}"
  fi
  for var in ANSIBLE_COLLECTIONS_PATH ANSIBLE_ROLES_PATH; do
    val="$(eval "echo \"\${${var}}\"")"
    log.debug "Checking environment ${var}: '${val}'"
  done
  IFS=',' read -r -a extra_vars <<<"${extra_vars_txt}"
  cmd+=(ansible-playbook -i localhost -c local)
  for extra_var in "${extra_vars[@]}"; do
    item="${extra_var}"
    test -r "${item}" && item="@${item}"
    cmd+=("-e" "${item}")
  done
  # log.debug "Current cmd: '${cmd[*]}'"
  log.debug "Updating cmd with: '${extra_params[*]}'"
  for extra_param in "${extra_params[@]}"; do
    cmd+=("${extra_param}")
  done
  # log.debug "Current cmd: '${cmd[*]}'"
  cmd+=("${playbook}")
  venv_activate "${venv_dir}"
  run_cmd 0 "${cmd[@]}"
  rc=$?
  epilog "${rc}"
  return "${rc}"
}

function action.test() {
  local \
    item \
    test_type \
    venv_dir \
    env_file \
    extra_vars \
    playbook \
    var \
    rc
  local -a \
    vars
  prolog "${@}"
  venv_dir="${1:-"${VENV_DIR}"}"
  vars+=(venv_dir)
  shift 1
  playbook="${1:-"${PLAYBOOK}"}"
  vars+=(playbook)
  shift 1
  test_type="${1:-"${TEST}"}"
  vars+=(test_type)
  shift 1
  env_file="${1:-"${FIXTURES_ROOT}/${test_type}/env.bash"}"
  vars+=(env_file)
  shift 1
  extra_vars="${1:-"${FIXTURES_ROOT}/${test_type}/${PLAYBOOK}"}"
  vars+=(extra_vars)
  shift 1
  for var in "${vars[@]}"; do
    val="$(eval "echo \$${var}" || true)"
    test -n "${val}" && log.debug "updated: ${var}='${val}'"
  done
  print_test_type_detection_var "${test_type}"
  source_script "${env_file}"
  rc=$?
  test "${rc}" -eq 0 || die "${rc}" "Failed during ${env_file} execution (sourcing). please check your environment."
  log.debug "sourced ${env_file} with rc=${rc}"
  print_test_type_detection_var "${test_type}"
  log.info "About to run test environment for ${test_type}, using extra_vars=${extra_vars}"
  action.run_playbook "${venv_dir}" "${playbook}" "${extra_vars}"
  rc=$?
  epilog "${rc}"
  return "${rc}"
}

function main() {
  local \
    action \
    rc
  local -a \
    reqs \
    debug_vars \
    args
  rc=0
  action="${1:-"bootstrap"}"
  log.info "Running action ${action}"
  # common args:
  args+=("${VENV_DIR}")

  debug_vars+=(
    SCRIPT_DBG
    DEV_MODE
    RECREATE
    PY
    VENV_DIR
    VARS_DIR
    # OUT_DIR
    # TPL_DIR
    # DATA_FILE
    # PLAYBOOK
    # GENERATOR
    # TPL_FILE
    EXTRA_VARS
    ANSIBLE_COLLECTIONS_PATH
    # CACHE_PATH
    TEST
    COLLECTION_ROOT
    COLLECTIONS_REQS_LOCAL
    COLLECTION_REQ_FILES_TXT
    # FIXTURES_ROOT
    TEST_DATA_DIR
    REQ_COLLECTIONS_ATTR
    # YQ_SEARCH_PREFIX
    # LIVE_FOREVER
  )

  if [[ "${SCRIPT_DBG}" -gt 0 ]]; then
    log.debug "Printing some debug VARIABLES:"
    for var_name in "${debug_vars[@]}"; do
      print_debug_var_name "${var_name}"
    done
  fi
  case "${action}" in
  "bootstrap")
    args+=("${PY}" "${ANSIBLE_COLLECTIONS_PATH}" "${RECREATE}" "${CACHE_PATH}")
    IFS=',' read -r -a reqs <<<"${COLLECTION_REQ_FILES_TXT}"
    log.debug "COLLECTION_REQ_FILES_TXT='${COLLECTION_REQ_FILES_TXT}'"
    log.debug "reqs: ${reqs[*]}"
    args+=("${reqs[@]}")
    time action.bootstrap "${args[@]}"
    rc=$?
    ;;
  "gendata")
    args+=("${DATA_FILE}" "${GENERATOR}" "${RECREATE}")
    time action.gendata "${args[@]}"
    rc=$?
    ;;
  "buildpkg")
    args+=("${RECREATE}" "${COLLECTION_ROOT}" "${COLLECTIONS_REQS_LOCAL}")
    time action.buildpkg "${args[@]}"
    rc=$?
    ;;
  "render")
    args+=("${DATA_FILE}" "${PLAYBOOK}" "${TPL_FILE}" "${VARS_DIR}/${PLAYBOOK##*/}")
    time action.render "${args[@]}"
    rc=$?
    ;;
  "run_playbook")
    args+=("${PLAYBOOK}")
    time action.run_playbook "${args[@]}"
    rc=$?
    ;;
  "test")
    TEST_DATA_DIR="${TEST_DATA_DIR:-"${FIXTURES_ROOT}/${TEST}"}"
    args+=("${PLAYBOOK}" "${TEST}")
    args+=("${TEST_DATA_DIR}/env.bash")
    args+=("${TEST_DATA_DIR}/${PLAYBOOK}")
    time action.test "${args[@]}"
    rc=$?
    ;;
  *)
    help "${action}"
    exit 1
    ;;
  esac
  if [[ "${rc}" -ne 0 ]]; then
    log.error "The action='${action}' failed with rc=${rc}"
  fi
  return "${rc}"
}

if [[ "$0" = "${BASH_SOURCE:-""}" ]]; then
  main "${@}"
  RC=$?
fi
exit "${RC}"
