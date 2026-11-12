#!/usr/bin/env python3
"""Require explicit OCP release pullspecs to be accepted by release-controller."""
import json
import re
import sys
import urllib.error
import urllib.request

BASE = 'https://openshift-release.apps.ci.l2s4.p1.openshiftapps.com/api/v1/releasestream/'


def check(image):
    # Release-controller records identify tagged pullspecs, not arbitrary
    # digest references. Internally pinned images are handled by the role.
    if '@' in image:
        raise ValueError('use the tagged release-controller pullspec to verify Accepted phase')
    tagged = image
    leaf = tagged.rsplit('/', 1)[-1]
    if ':' not in leaf:
        raise ValueError('a release-version tag is required to verify Accepted phase')
    version = re.search(r'(?<!\d)(\d+)\.(\d+)\.\d+', leaf.rsplit(':', 1)[1])
    if not version:
        raise ValueError('the image tag must contain an OCP release version')
    major, minor = version.group(1), version.group(2)
    streams = [f'{major}-stable', f'{major}-dev-preview',
               f'{major}.{minor}.0-0.nightly', f'{major}.{minor}.0-0.ci']
    phases = set()
    unavailable = []
    for stream in streams:
        try:
            with urllib.request.urlopen(BASE + stream + '/tags', timeout=30) as response:
                tags = json.load(response).get('tags', [])
        except (OSError, ValueError, urllib.error.HTTPError) as exc:
            unavailable.append(f'{stream}: {type(exc).__name__}')
            continue
        for tag in tags:
            if tag.get('pullSpec') == tagged:
                phase = tag.get('phase', '')
                if phase == 'Accepted':
                    print(f'Accepted OCP release: {tag.get("name", "unknown")} ({stream})')
                    return
                phases.add(phase or 'unknown')
    if phases:
        raise ValueError('release is not Accepted (phase: ' + ', '.join(sorted(phases)) + ')')
    if unavailable:
        raise ValueError('could not verify release phase; unavailable streams: ' + ', '.join(unavailable))
    raise ValueError('image is not listed in an OCP release stream')


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--json':
        images = json.loads(sys.argv[2])
        if not isinstance(images, list) or not all(isinstance(image, str) for image in images):
            raise ValueError('expected a JSON list of image pullspecs')
    elif len(sys.argv) == 2:
        images = [sys.argv[1]]
    else:
        raise ValueError('usage: check-accepted-release.py PULLSPEC | --json JSON_LIST')
    for image in dict.fromkeys(images):
        check(image)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f'Cannot verify OCP release: {exc}', file=sys.stderr)
        sys.exit(1)
