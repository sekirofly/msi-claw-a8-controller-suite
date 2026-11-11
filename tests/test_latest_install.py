"""Exercise latest-release discovery without network access or device changes."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LatestInstallTests(unittest.TestCase):
    def run_bootstrap(self, metadata, *args):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / 'release.json').write_text(json.dumps(metadata))
            curl = directory / 'curl'
            curl.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
root = pathlib.Path(os.environ['SUITE_BOOTSTRAP_FIXTURE'])
url = next(arg for arg in sys.argv[1:] if arg.startswith('https://'))
with (root / 'calls').open('a') as calls:
    calls.write(url + '\\n')
output = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])
if url.endswith('/releases/latest'):
    output.write_bytes((root / 'release.json').read_bytes())
elif url == 'https://raw.githubusercontent.com/sekirofly/msi-claw-a8-controller-suite/v9.8.7/installer.py':
    output.write_text('import json, sys; print(json.dumps(sys.argv[1:]))')
else:
    raise SystemExit(22)
''')
            curl.chmod(0o755)
            env = {**os.environ, 'PATH': str(directory) + os.pathsep + os.environ['PATH'],
                   'SUITE_BOOTSTRAP_FIXTURE': str(directory)}
            result = subprocess.run(['bash', str(ROOT / 'install-latest.sh'), *args],
                                    env=env, text=True, capture_output=True)
            return result, (directory / 'calls').read_text().splitlines()

    def test_downloads_installer_from_published_tag_and_preserves_arguments(self):
        result, calls = self.run_bootstrap(
            {'tag_name': 'v9.8.7', 'draft': False, 'prerelease': False},
            'install', '--decky-home', '/tmp/home with spaces')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout),
                         ['install', '--decky-home', '/tmp/home with spaces'])
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[1].endswith('/v9.8.7/installer.py'))

    def test_rejects_unpublished_prerelease_and_invalid_tags(self):
        for overrides in ({'draft': True}, {'prerelease': True},
                          {'tag_name': 'v9.8.7-alpha.1'}, {'tag_name': '../main'},
                          {'tag_name': ''}):
            with self.subTest(overrides=overrides):
                result, calls = self.run_bootstrap(
                    {'tag_name': 'v9.8.7', 'draft': False, 'prerelease': False, **overrides})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('No published stable release found', result.stderr)
                self.assertEqual(len(calls), 1)
