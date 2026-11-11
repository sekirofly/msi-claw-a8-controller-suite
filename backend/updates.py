"""Manual, read-only checks using the same system curl as the installer entry point."""
import json
import re
import subprocess

REPO = 'https://github.com/sekirofly/msi-claw-a8-controller-suite'
API = 'https://api.github.com/repos/sekirofly/msi-claw-a8-controller-suite/releases/latest'
LIMIT = 256 * 1024


class SourceError(ValueError):
    pass


class UpdateCheckError(ValueError):
    def __init__(self, api, fallback):
        self.failures = {'api': api, 'fallback': fallback}
        super().__init__(f'API: {api}; release page: {fallback}')


def version_key(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:-alpha\.(\d+))?', value)
    if not match:
        raise ValueError('Invalid release version')
    major, minor, patch, alpha = match.groups()
    return (int(major), int(minor), int(patch), alpha is None, int(alpha or 0))


def curl(url, current, head=False):
    command = ['/usr/bin/curl', '--silent', '--show-error', '--fail', '--location',
               '--proto', '=https', '--proto-redir', '=https', '--max-redirs', '3',
               '--connect-timeout', '5', '--max-time', '10', '--max-filesize', str(LIMIT),
               '--user-agent', 'msi-claw-a8-controller-suite/' + current]
    if head:
        command += ['--head', '--output', '/dev/null', '--write-out', '%{http_code}\n%{url_effective}']
    else:
        command += ['--header', 'Accept: application/vnd.github+json', '--write-out', '\n%{http_code}']
    try:
        response = subprocess.run([*command, url], capture_output=True, timeout=12, check=False)
    except FileNotFoundError:
        raise SourceError('curl_missing') from None
    except subprocess.TimeoutExpired:
        raise SourceError('timeout') from None
    if response.returncode:
        code = {5: 'proxy', 6: 'dns', 7: 'connection', 28: 'timeout', 35: 'tls',
                47: 'redirects', 60: 'tls_certificate', 63: 'response_too_large'}.get(response.returncode)
        if response.returncode == 22:
            status = re.search(rb'(?:^|\n)([45][0-9]{2})(?:\n|$)', response.stdout)
            code = 'http_' + status[1].decode() if status else 'http_error'
        raise SourceError(code or 'curl_' + str(response.returncode))
    return response.stdout


def api_tag(current):
    data, status = curl(API, current).rsplit(b'\n', 1)
    if status != b'200' or len(data) > LIMIT:
        raise SourceError('invalid_response')
    release = json.loads(data)
    tag = release.get('tag_name', '')
    if (release.get('draft') is not False or release.get('prerelease') is not False
            or not isinstance(tag, str) or not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', tag)):
        raise SourceError('invalid_response')
    return tag


def page_tag(current):
    # GitHub redirects /releases/latest to the published stable release without
    # consuming the API quota. HEAD follows that redirect without downloading HTML.
    response = curl(REPO + '/releases/latest', current, head=True).decode().strip()
    match = re.fullmatch(r'200\n' + re.escape(REPO) + r'/releases/tag/(v[0-9]+\.[0-9]+\.[0-9]+)', response)
    if not match:
        raise SourceError('invalid_response')
    return match[1]


def reason(exc):
    return str(exc) if isinstance(exc, SourceError) else 'invalid_response'


def check_latest(current):
    version_key(current)
    try:
        tag = api_tag(current)
    except Exception as api_error:
        api_reason = reason(api_error)
        try:
            tag = page_tag(current)
        except Exception as fallback_error:
            raise UpdateCheckError(api_reason, reason(fallback_error)) from None
    return {'current': current, 'latest': tag[1:],
            'available': version_key(tag) > version_key(current)}
