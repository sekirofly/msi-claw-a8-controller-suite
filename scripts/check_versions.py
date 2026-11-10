"""One version, five places. Fail loudly instead of shipping a broken install.

``package.json`` is the source of truth:
- ``plugin.json`` is what Decky displays,
- ``installer.py`` decides which release tag it downloads,
- ``install.sh`` pins the raw URL that fetches ``installer.py``,
- the panel prints it in Maintenance.

A disagreement in the last three breaks installation rather than display, so it
must fail here instead of at a user's terminal.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r'\d+\.\d+\.\d+(?:-alpha\.\d+)?')


def find(pattern, relative, flags=0):
    text = (ROOT / relative).read_text(encoding='utf-8')
    match = re.search(pattern, text, flags)
    return match.group(1) if match else None


def main():
    version = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version']
    if not VERSION_RE.fullmatch(version):
        print(f'FAIL package.json version {version!r} is not X.Y.Z or X.Y.Z-alpha.N')
        return 1
    checks = [
        ('plugin.json', find(r'"version"\s*:\s*"([^"]+)"', 'plugin.json')),
        ('installer.py', find(r'^VERSION\s*=\s*"([^"]+)"', 'installer.py', re.MULTILINE)),
        ('install.sh', find(r'/v(\d+\.\d+\.\d+(?:-alpha\.\d+)?)/installer\.py', 'install.sh')),
        ('src/index.tsx', find(r"'(\d+\.\d+\.\d+(?:-alpha\.\d+)?) · GPL", 'src/index.tsx')),
    ]
    failed = False
    for name, found in checks:
        ok = found == version
        failed = failed or not ok
        print(f'{"ok  " if ok else "FAIL"} {name}: {found!r}')
    if failed:
        print(f'Versions disagree; package.json says {version!r}. Update the files above.')
        return 1
    print(f'Versions consistent at {version}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
