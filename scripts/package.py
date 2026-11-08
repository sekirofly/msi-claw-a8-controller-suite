"""Preview archive with installer, rebuildable sources and dependency licenses."""
from pathlib import Path
import hashlib
import zipfile
import importlib.metadata
import yaml

root = Path(__file__).resolve().parents[1]
output = root / 'release'
output.mkdir(exist_ok=True)
archive = output / 'msi-claw-a8-controller-suite.zip'
prefix = 'msi-claw-a8-controller-suite/'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
    for name in ('main.py','recover.py','installer.py','install.sh','diagnostics.sh','maintenance_runner.py','plugin.json','package.json','pnpm-lock.yaml',
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
    assert yaml.__version__ == '6.0.3'
    yaml_root = Path(yaml.__file__).parent
    # Pure Python only: no wheel-specific native library or ABI dependency.
    for source in yaml_root.glob('*.py'):
        bundle.write(source, prefix + 'py_modules/yaml/' + source.name)
    distribution = importlib.metadata.distribution('PyYAML')
    licenses = [file for file in distribution.files if str(file).endswith('/LICENSE')]
    assert licenses
    bundle.write(distribution.locate_file(licenses[0]), prefix + 'third_party/PyYAML-LICENSE')
archive.with_suffix('.zip.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
print(archive)
