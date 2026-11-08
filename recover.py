"""Explicit terminal recovery, independent of Steam/Decky navigation."""
import argparse
from pathlib import Path
from backend.hardware import Hardware
from backend.inputplumber import InputPlumber

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--settings-dir', required=True, type=Path)
    args = parser.parse_args()
    snapshot = args.settings_dir / 'recovery.json'
    if not snapshot.is_file():
        raise SystemExit('No recovery snapshot found. No devices changed.')
    InputPlumber(Hardware(), snapshot).restore()
    print('Original InputPlumber profile and target devices restored. Hardware rumble and back-button mode were not reset.')
