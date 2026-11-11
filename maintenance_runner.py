"""Root-owned temporary runner, launched by systemd independently of Decky."""
from pathlib import Path
import shutil
import subprocess
import argparse
import re
import installer

def run(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--update-version')
    options, remaining = parser.parse_known_args(argv)
    original = installer.VERSION
    try:
        if options.update_version is not None:
            version = options.update_version
            if (not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version)
                    or not remaining or remaining[0] != 'install'
                    or '--reset-controller' in remaining):
                raise ValueError('Invalid update request')
            target = tuple(map(int, version.split('.')))
            current = tuple(map(int, original.split('-')[0].split('.')))
            if target < current or (target == current and '-alpha.' not in original):
                raise ValueError('Update must select a newer stable release')
            # A fresh independent process pins the existing verified download and
            # rollback flow to the release the user explicitly confirmed.
            installer.VERSION = version
        installer.main(remaining)
    finally:
        installer.VERSION = original


if __name__ == '__main__':
    try:
        run()
    except Exception:
        # Even a download failure must release the old plugin's pending state.
        # The independent job/journal retains the actual error for diagnosis.
        subprocess.run(['systemctl', 'restart', 'plugin_loader.service'], check=False, timeout=60)
        raise
    finally:
        directory = Path(__file__).resolve().parent
        if directory.parent == Path('/run') and directory.name.startswith('msi-claw-a8-controller-suite-maintenance-'):
            shutil.rmtree(directory)
