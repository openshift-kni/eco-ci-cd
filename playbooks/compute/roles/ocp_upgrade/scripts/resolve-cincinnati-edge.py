#!/usr/bin/env python3
"""Select a release image from the Cincinnati upgrade graph."""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request


GRAPH_URL = 'https://api.openshift.com/api/upgrades_info/v1/graph'
NUMERIC_VERSION = re.compile(r'^\d+\.\d+\.\d+$')
DIGEST_IMAGE = re.compile(r'^[^\s@]+@sha256:[0-9a-f]{64}$')


def graph_edges(graph):
    """Return graph edges whose source and target both exist as nodes."""
    nodes = graph['nodes']
    known = {node.get('version') for node in nodes}
    edges = []
    for source, target in graph.get('edges', []):
        if 0 <= source < len(nodes) and 0 <= target < len(nodes):
            edges.append((nodes[source].get('version'), nodes[target].get('version')))
    for group in graph.get('conditionalEdges') or []:
        edges.extend((edge.get('from'), edge.get('to')) for edge in group.get('edges') or [])
    return [(source, target) for source, target in edges
            if isinstance(source, str) and isinstance(target, str) and source in known and target in known]


def select_version(graph, mode, current, from_version, target, then_version):
    edges = graph_edges(graph)
    reachable = set()
    if then_version:
        reachable = {source for source, dest in edges
                     if dest.startswith(then_version + '.') and NUMERIC_VERSION.fullmatch(source)}
    candidates = [(source, dest) for source, dest in edges
                  if dest.startswith(target + '.') and NUMERIC_VERSION.fullmatch(dest)
                  and (not then_version or dest in reachable)]
    if mode == 'edge':
        candidates = [(source, dest) for source, dest in candidates if source == current]
        return max((dest for _, dest in candidates), key=lambda value: int(value.split('.')[2]), default='')
    candidates = [(source, dest) for source, dest in candidates
                  if source.startswith(from_version + '.') and NUMERIC_VERSION.fullmatch(source)]
    selected = max(candidates, key=lambda edge: (int(edge[0].split('.')[2]), int(edge[1].split('.')[2])), default=None)
    return selected[0] if selected else ''


def fetch_graph(channel):
    url = GRAPH_URL + '?' + urllib.parse.urlencode({'channel': channel, 'arch': 'amd64'})
    request = urllib.request.Request(url, headers={'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def log_conditional_risks(graph, current, version):
    for group in graph.get('conditionalEdges') or []:
        if any(edge.get('from') == current and edge.get('to') == version for edge in group.get('edges') or []):
            print('[WARN] Conditional graph edge; check cluster risk recommendations.', file=sys.stderr)
            for risk in group.get('risks') or []:
                name = risk.get('name') or 'UnknownRisk'
                message = risk.get('message') or ''
                url = risk.get('url') or ''
                print(f'[WARN] {name}: {message} {url}', file=sys.stderr)


def eus_path(from_version, to_version):
    start = tuple(int(part) for part in from_version.split('.'))
    target = tuple(int(part) for part in to_version.split('.'))
    if start[0] == target[0]:
        return f'{start[0]}.{start[1] + 1}', to_version
    return to_version, ''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('edge', 'install', 'eus-install'))
    parser.add_argument('--channel', default='')
    parser.add_argument('--from', dest='from_version', default='')
    parser.add_argument('--target', default='')
    parser.add_argument('--then', dest='then_version', default='')
    parser.add_argument('--current', default='')
    parser.add_argument('--to', default='')
    args = parser.parse_args()

    mode = args.mode
    if mode == 'eus-install':
        first_hop, then_version = eus_path(args.from_version, args.to)
        channel, target = 'eus-' + args.to, first_hop
        mode = 'install'
    else:
        channel, target, then_version = args.channel, args.target, args.then_version
        if not channel or not target or (mode == 'install' and not args.from_version):
            parser.error('channel and target are required; install also requires --from')

    graph = fetch_graph(channel)
    current = args.current
    if mode == 'edge' and not current:
        current = subprocess.run(['oc', 'get', 'clusterversion', 'version', '-o', 'jsonpath={.status.desired.version}'],
                                 check=True, stdout=subprocess.PIPE, text=True).stdout.strip()
    version = select_version(graph, mode, current, args.from_version, target, then_version)
    if not version:
        start = current if mode == 'edge' else args.from_version + '.z'
        next_hop = f' (then {then_version})' if then_version else ''
        raise ValueError(f'No Cincinnati edge {start} -> {target}.z on {channel}{next_hop}')

    tagged = f'quay.io/openshift-release-dev/ocp-release:{version}-x86_64'
    payload = tagged
    graph_payload = ''
    if mode == 'edge':
        graph_payload = next((node.get('payload') for node in graph['nodes']
                              if node.get('version') == version and node.get('payload')), '')
        if isinstance(graph_payload, str) and DIGEST_IMAGE.fullmatch(graph_payload):
            payload = graph_payload
        print(f'[INFO] Cincinnati {channel}: {current} -> {version}.', file=sys.stderr)
        log_conditional_risks(graph, current, version)
    else:
        print(f'[INFO] Planning {version} from the Cincinnati graph.', file=sys.stderr)

    if mode == 'edge' and os.environ.get('OCP_CINCINNATI_INCLUDE_TAG') == 'true':
        print(tagged)
        if graph_payload:
            print(graph_payload)
    else:
        print(payload)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(f'[ERROR] Cincinnati resolver failed: {error}', file=sys.stderr)
        sys.exit(1)
