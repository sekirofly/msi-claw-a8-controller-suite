"""Manual, read-only checks for published stable releases."""
import json
import re
import urllib.request

REPO = 'https://github.com/sekirofly/msi-claw-a8-controller-suite'
API = 'https://api.github.com/repos/sekirofly/msi-claw-a8-controller-suite/releases/latest'


def version_key(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:-alpha\.(\d+))?', value)
    if not match:
        raise ValueError('Invalid release version')
    major, minor, patch, alpha = match.groups()
    return (int(major), int(minor), int(patch), alpha is None, int(alpha or 0))


def check_latest(current):
    request = urllib.request.Request(API, headers={
        'User-Agent': 'msi-claw-a8-controller-suite/' + current,
        'Accept': 'application/vnd.github+json',
    })
    with urllib.request.urlopen(request, timeout=10) as response:
        data = response.read(256 * 1024 + 1)
    if len(data) > 256 * 1024:
        raise ValueError('Release response exceeds size limit')
    release = json.loads(data)
    tag = release.get('tag_name', '')
    if (release.get('draft') is not False or release.get('prerelease') is not False
            or not isinstance(tag, str) or not re.fullmatch(r'v\d+\.\d+\.\d+', tag)):
        raise ValueError('No published stable release')
    return {'current': current, 'latest': tag[1:],
            'available': version_key(tag) > version_key(current)}
