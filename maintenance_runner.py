"""Root-owned temporary runner, launched by systemd independently of Decky."""
from pathlib import Path
import shutil
from installer import main

if __name__ == '__main__':
    try:
        main()
    finally:
        directory = Path(__file__).resolve().parent
        if directory.parent == Path('/run') and directory.name.startswith('msi-claw-a8-controller-suite-maintenance-'):
            shutil.rmtree(directory)
