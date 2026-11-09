"""Explicit terminal recovery, independent of Steam/Decky navigation."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / 'py_modules'))
from backend.hardware import Hardware
from backend.inputplumber import InputPlumber

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--settings-dir', required=True, type=Path)
    args = parser.parse_args()
    ip = InputPlumber(Hardware(), args.settings_dir / 'management.json')
    ip.set_enabled(False)
    ip.restore()
    print('Installed system InputPlumber defaults restored. Hardware rumble and back-button mode were not reset.')
