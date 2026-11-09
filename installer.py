#!/usr/bin/env python3
"""MSI Claw A8 Controller Suite installer. Python standard library; Linux/systemd only."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tempfile
import urllib.request
import zipfile

VERSION = "0.1.0-alpha.2"
REPO = "https://github.com/sekirofly/msi-claw-a8-controller-suite"
NAME = "MSI Claw A8 Controller Suite"
FOLDER = "msi-claw-a8-controller-suite"
SERVICE = "plugin_loader.service"


def fetch(url, limit=16 * 1024 * 1024):
    request = urllib.request.Request(url, headers={"User-Agent": "msi-claw-a8-controller-suite/" + VERSION})
    with urllib.request.urlopen(request, timeout=45) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Download exceeds size limit")
    return data


def unpack(data, destination):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        total = 0
        seen = set()
        for entry in archive.infolist():
            path = PurePosixPath(entry.filename)
            total += entry.file_size
            if (path.is_absolute() or ".." in path.parts or "\\" in entry.filename
                    or not path.parts or path.parts[0] != FOLDER
                    or stat.S_ISLNK(entry.external_attr >> 16)
                    or entry.filename in seen or total > 32 * 1024 * 1024):
                raise ValueError("Unsafe release archive")
            seen.add(entry.filename)
        archive.extractall(destination)
    root = destination / FOLDER
    for required in ("main.py", "plugin.json", "package.json", "dist/index.js", "installer.py", "recover.py", "backend/inputplumber.py", "py_modules/yaml/__init__.py"):
        if not (root / required).is_file():
            raise ValueError("Incomplete release: " + required)
    manifest = json.loads((root / "plugin.json").read_text())
    package = json.loads((root / "package.json").read_text())
    if manifest['name'] != NAME or package['name'] != FOLDER:
        raise ValueError("Wrong plugin identity")
    if manifest['version'] != VERSION or package['version'] != VERSION:
        raise ValueError("Release version mismatch")
    return root


def validate_home(home):
    home = Path(home).absolute()
    home = home.resolve(strict=True)
    if home == Path('/'):
        raise ValueError("Decky home cannot be the filesystem root")
    if not (home / "plugins").is_dir():
        raise ValueError("Decky not found. Install Decky first or pass --decky-home.")
    for section in ("plugins", "settings", "data", "logs"):
        parent = home / section
        if parent.is_symlink():
            raise ValueError("Refusing symlink: " + str(parent))
        child = parent / FOLDER
        if child.is_symlink():
            raise ValueError("Refusing symlink: " + str(child))
    target = home / "plugins" / FOLDER
    if target.exists():
        if json.loads((target / 'plugin.json').read_text())['name'] != NAME:
            raise ValueError("Existing directory belongs to another plugin")
    for candidate in (home / 'plugins').iterdir():
        manifest = candidate / 'plugin.json'
        if candidate != target and manifest.is_file():
            try:
                if json.loads(manifest.read_text())['name'] == NAME:
                    raise ValueError("MSI Claw A8 Controller Suite uses a different folder; uninstall it through Decky first")
            except (json.JSONDecodeError, KeyError):
                continue
    return home


def service(action):
    subprocess.run(["systemctl", action, SERVICE], check=True, timeout=60)


def restore_before_removal(home, staged=None):
    """Called only after Decky is stopped. Fail before moving/deleting any files."""
    settings = home / 'settings' / FOLDER
    snapshot = settings / 'recovery.json'
    if not snapshot.exists():
        return
    if snapshot.is_symlink():
        raise ValueError('Refusing symlink recovery snapshot')
    data = json.loads(snapshot.read_text(encoding='utf-8'))
    if not data.get('active'):
        return
    recovery_dir = home / ('.' + FOLDER + '-recovery')
    if recovery_dir.is_symlink():
        raise ValueError('Refusing symlink recovery directory')
    recovery_dir.mkdir(exist_ok=True, mode=0o700)
    import time
    backup = recovery_dir / ('snapshot-' + str(time.time_ns()) + '.json')
    shutil.copyfile(snapshot, backup)
    backup.chmod(0o600)
    preference = settings / 'management.json'
    enabled = json.loads(preference.read_text())['enabled'] if preference.exists() else True
    target = home / 'plugins' / FOLDER
    helper_root = target if (target / 'recover.py').is_file() else staged
    if helper_root is None:
        raise ValueError('Active recovery snapshot exists but recovery code is missing; files preserved')
    try:
        subprocess.run(['python3', str(helper_root / 'recover.py'), '--settings-dir', str(settings)],
                       check=True, timeout=90)
        if json.loads(snapshot.read_text(encoding='utf-8')).get('active'):
            raise ValueError('Recovery did not complete; files preserved')
    finally:
        # Maintenance restoration is temporary, including a failed update rollback.
        temporary = preference.with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump({'enabled': enabled}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, preference)


def transact(home, action, staged=None):
    """Move only this plugin's directories; roll back if service restart fails."""
    home = validate_home(home)
    target = home / 'plugins' / FOLDER
    paths = [target]
    if action in ('uninstall', 'reinstall'):
        paths += [home / section / FOLDER for section in ('settings', 'data', 'logs')]
    backup = Path(tempfile.mkdtemp(prefix='.msi-claw-a8-controller-suite-backup-', dir=home))
    moved = []
    install_started = False
    stopped = False
    cleanup = False
    try:
        service('stop')
        stopped = True
        restore_before_removal(home, staged)
        for index, path in enumerate(paths):
            if path.exists():
                saved = backup / str(index)
                path.rename(saved)
                moved.append((path, saved))
        if staged is not None:
            install_started = True
            shutil.copytree(staged, target)
            for path in [target, *target.rglob('*')]:
                os.chown(path, 0, 0)
                path.chmod(0o755 if path.is_dir() else 0o644)
        service('start')
        service('is-active')
        cleanup = True
    except Exception:
        if stopped:
            service('stop')
            if target.exists() and install_started:
                shutil.rmtree(target)
            for path, saved in reversed(moved):
                # A failed service start may have recreated its log/settings folder.
                if path.exists() and path != target:
                    if path.is_symlink() or not path.is_dir():
                        raise ValueError('Unexpected path during rollback: ' + str(path))
                    shutil.rmtree(path)
                path.parent.mkdir(parents=True, exist_ok=True)
                saved.rename(path)
            service('start')
        cleanup = True
        raise
    finally:
        # Preserve recovery material if rollback itself failed.
        if cleanup:
            shutil.rmtree(backup)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'reinstall', 'uninstall'], nargs='?', default='install')
    parser.add_argument('--decky-home', default=str(Path.home() / 'homebrew'))
    args = parser.parse_args()
    home = validate_home(args.decky_home)
    if os.geteuid() != 0:
        os.execvp('sudo', ['sudo', 'python3', str(Path(__file__).resolve()), args.action, '--decky-home', str(home)])
    import fcntl
    with open('/run/msi-claw-a8-controller-suite.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with tempfile.TemporaryDirectory(prefix='msi-claw-a8-controller-suite-') as directory:
            staged = None
            if args.action != 'uninstall':
                base = REPO + '/releases/download/v' + VERSION + '/'
                data = fetch(base + 'msi-claw-a8-controller-suite.zip')
                expected = fetch(base + 'msi-claw-a8-controller-suite.zip.sha256', 1024).decode().split()[0]
                if len(expected) != 64 or hashlib.sha256(data).hexdigest() != expected:
                    raise ValueError('Release checksum mismatch; existing installation unchanged')
                staged = unpack(data, Path(directory))
            transact(home, args.action, staged)
    print('MSI Claw A8 Controller Suite: ' + args.action + ' complete. Hardware settings unchanged.')
    print('Preview release: disable/remove the original DeckyPlumber and Back Buttons & Rumble plugins before enabling management. Existing suite button configurations are kept on install/update; clean reinstall/uninstall removes them after recovery.')
    print('IMPORTANT: Save your work and reboot normally before returning to Gaming Mode. Controller detection after a live Decky restart is not reliable on the tested A8.')
    if args.action != 'uninstall':
        print('If rumble or controller behavior remains abnormal after reboot, an EC reset may be needed. It resolved a reported loss of rumble on the tested A8; it is not required for every installation.')
        print('Follow MSI official EC reset guidance: https://www.msi.com/support/technical_details/HH_EC_Reset')


if __name__ == '__main__':
    main()

