"""Development archive with rebuildable source and bundled API license/source.

This is not an installer or production release.
"""
from pathlib import Path
import hashlib
import zipfile

root = Path(__file__).resolve().parents[1]
output = root / 'release'
output.mkdir(exist_ok=True)
archive = output / 'msi-claw-a8-controller-suite-development.zip'
prefix = 'msi-claw-a8-controller-suite/'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
    for name in ('main.py','recover.py','plugin.json','package.json','pnpm-lock.yaml',
                 'rollup.config.js','tsconfig.json','LICENSE','README.md','README.zh-CN.md',
                 'THIRD_PARTY.md','implementation-status.zh-CN.md','dist/index.js'):
        bundle.write(root / name, prefix + name)
    for folder in ('src','backend','docs','tests','scripts','third_party'):
        for source in (root / folder).rglob('*'):
            if source.is_file() and '__pycache__' not in source.parts:
                bundle.write(source, prefix + source.relative_to(root).as_posix())
    api = root / 'node_modules/@decky/api'
    for name in ('LICENSE','package.json'):
        bundle.write(api / name, prefix + 'third_party/decky-api/' + name)
    for source in (api / 'src').rglob('*'):
        if source.is_file():
            bundle.write(source, prefix + 'third_party/decky-api/' + source.relative_to(api).as_posix())
archive.with_suffix('.zip.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
print(archive)
