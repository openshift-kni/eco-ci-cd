#!/bin/bash
# Pick an OpenShift release pullspec from the Cincinnati upgrade graph.
#
#   edge    cluster's current version -> highest z-stream of --target on --channel
#   install highest --from z-stream that has an edge to --target (optional --then)
#
# Prints only the pullspec on stdout. Diagnostics go to stderr.
# OCP_UPGRADE_GRAPH_V1
set -euo pipefail

usage() {
    echo "Usage: $0 edge --channel CHANNEL --target MAJOR.MINOR [--current VERSION] [--then MAJOR.MINOR]" >&2
    echo "       $0 install --channel CHANNEL --from MAJOR.MINOR --target MAJOR.MINOR [--then MAJOR.MINOR]" >&2
    exit 2
}

mode="${1:-}"
shift || usage

channel=""
target=""
from_version=""
then_version=""
current=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --channel) channel="${2:-}"; shift 2 ;;
        --target) target="${2:-}"; shift 2 ;;
        --from) from_version="${2:-}"; shift 2 ;;
        --then) then_version="${2:-}"; shift 2 ;;
        --current) current="${2:-}"; shift 2 ;;
        *) usage ;;
    esac
done

[[ -n "${channel}" && -n "${target}" ]] || usage
case "${mode}" in
    edge) ;;
    install) [[ -n "${from_version}" ]] || usage ;;
    *) usage ;;
esac

graph_url="https://api.openshift.com/api/upgrades_info/v1/graph?channel=${channel}&arch=amd64"
graph="$(mktemp)"
trap 'rm -f "${graph}"' EXIT

if ! curl -fsSL -H 'Accept: application/json' "${graph_url}" -o "${graph}"; then
    echo "[ERROR] Cincinnati graph request failed: ${graph_url}" >&2
    exit 1
fi

if [[ "${mode}" == "edge" && -z "${current}" ]]; then
    current="$(oc get clusterversion version -o jsonpath='{.status.desired.version}')"
fi

version="$(jq -r \
    --arg mode "${mode}" \
    --arg current "${current}" \
    --arg from_prefix "${from_version}." \
    --arg target_prefix "${target}." \
    --arg then_prefix "${then_version:+${then_version}.}" \
    '
    def numeric: test("^[0-9]+\\.[0-9]+\\.[0-9]+$");
    def zkey: split(".")[2] | tonumber;
    . as $g
    | [ $g.nodes[]?.version ] as $known
    | [ $g.edges[] | {
        fv: $g.nodes[.[0]].version,
        tv: $g.nodes[.[1]].version
      } ] as $unconditional
    | [ $g.conditionalEdges[]? | .edges[]? | {fv: .from, tv: .to} ] as $conditional
    | (($unconditional + $conditional)
       | map(. as $edge | select(($known | index($edge.fv)) != null and ($known | index($edge.tv)) != null))) as $possible
    | (if $then_prefix == "" then []
       else [$possible[] | select((.tv | startswith($then_prefix)) and (.fv | numeric)) | .fv] | unique
       end) as $reachable
    | if $mode == "edge" then
        $possible
        | map(select(.fv == $current and (.tv | startswith($target_prefix)) and (.tv | numeric)
            and (if $then_prefix == "" then true else (.tv as $tv | $reachable | index($tv) != null) end)))
        | sort_by(.tv | zkey)
        | last
        | .tv // empty
      else
        $possible | map(select(
            (.fv | startswith($from_prefix)) and (.fv | numeric)
            and (.tv | startswith($target_prefix)) and (.tv | numeric)
            and (if $then_prefix == "" then true else (.tv as $tv | $reachable | index($tv) != null) end)
          ))
        | sort_by([(.fv | zkey), (.tv | zkey)])
        | last
        | .fv // empty
      end
    ' "${graph}")"

if [[ -z "${version}" || "${version}" == "null" ]]; then
    if [[ "${mode}" == "edge" ]]; then
        echo "[ERROR] No Cincinnati edge ${current} -> ${target}.z on ${channel}." >&2
    else
        echo "[ERROR] No Cincinnati edge ${from_version}.z -> ${target}.z on ${channel}${then_version:+ (then ${then_version})}." >&2
    fi
    echo "[ERROR] Graph: ${graph_url}" >&2
    echo "[ERROR] Use a source release with a supported edge or provide an explicitly approved hop image." >&2
    exit 1
fi

payload="quay.io/openshift-release-dev/ocp-release:${version}-x86_64"

if [[ "${mode}" == "edge" ]]; then
    graph_payload="$(jq -r --arg version "${version}" '[.nodes[]? | select(.version == $version) | .payload // empty] | first // empty' "${graph}")"
    if [[ "${graph_payload}" =~ ^[^[:space:]@]+@sha256:[0-9a-f]{64}$ ]]; then
        payload="${graph_payload}"
    fi
    echo "[INFO] Cincinnati ${channel}: ${current} -> ${version}." >&2
    jq -r --arg from "${current}" --arg to "${version}" '
      .conditionalEdges[]? | select(any(.edges[]?; .from == $from and .to == $to))
      | "[WARN] Conditional graph edge; check cluster risk recommendations.",
        (.risks[]? | "[WARN] \(.name // "UnknownRisk"): \(.message // "") \(.url // "")")
    ' "${graph}" >&2
else
    echo "[INFO] Planning ${version} from the Cincinnati graph." >&2
fi

printf '%s\n' "${payload}"
