"""Verify the actual release archive, including a no-site-packages YAML import."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import installer

archive = Path(__file__).resolve().parents[1] / 'release' / (installer.FOLDER + '.zip')
data = archive.read_bytes()
assert hashlib.sha256(data).hexdigest() == archive.with_suffix('.zip.sha256').read_text().split()[0]
with zipfile.ZipFile(archive) as bundle:
    # Decky's local ZIP installer discovers exactly one top-level plugin.json.
    manifests = [name for name in bundle.namelist()
                 if name.endswith('/plugin.json') and name.count('/') == 1]
    assert manifests == [installer.FOLDER + '/plugin.json']
with tempfile.TemporaryDirectory() as temporary:
    root = installer.unpack(data, Path(temporary))
    manifest = json.loads((root / 'plugin.json').read_text())
    package = json.loads((root / 'package.json').read_text())
    assert 'root' in manifest['flags']
    # remote_binary entries make Decky download dependencies even for local ZIPs.
    assert not package.get('remote_binary'), 'Decky local installation must work offline'
    subprocess.run([sys.executable, '-I', '-S', '-c',
                    'import sys; sys.path.insert(0, sys.argv[1]); import yaml; '
                    'assert yaml.__version__ == "6.0.3"; '
                    'assert not yaml.__with_libyaml__; '
                    'assert yaml.safe_load("mapping: []") == {"mapping": []}',
                    str(root / 'py_modules')], check=True)
    assert (root / 'third_party/PyYAML-LICENSE').is_file()
    assert (root / 'third_party/decky-api/LICENSE').is_file()
print('Archive identity, version, checksum, licenses, Decky local ZIP compatibility and isolated pure-Python YAML import verified.')
