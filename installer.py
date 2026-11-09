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
import urllib.error
import time
import zipfile

VERSION = "0.1.0-alpha.13"
REPO = "https://github.com/sekirofly/msi-claw-a8-controller-suite"
NAME = "MSI Claw A8 Controller Suite"
FOLDER = "msi-claw-a8-controller-suite"
SERVICE = "plugin_loader.service"


def read_url(url, limit, accept=None):
    headers = {"User-Agent": "msi-claw-a8-controller-suite/" + VERSION}
    if accept:
        headers['Accept'] = accept
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=45) as response:
                data = response.read(limit + 1)
            if len(data) > limit:
                raise ValueError("Download exceeds size limit")
            return data
        except (urllib.error.URLError, TimeoutError) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in (408, 429, 500, 502, 503, 504):
                raise
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def fetch(url, limit=16 * 1024 * 1024):
    try:
        return read_url(url, limit)
    except (urllib.error.URLError, TimeoutError):
        prefix = REPO + '/releases/download/v' + VERSION + '/'
        name = url.removeprefix(prefix)
        if not url.startswith(prefix) or name not in (FOLDER + '.zip', FOLDER + '.zip.sha256'):
            raise
        # Public GitHub API route; no token, third-party mirror or verification bypass.
        print('Release download unavailable; trying GitHub asset API...')
        api = 'https://api.github.com/repos/sekirofly/msi-claw-a8-controller-suite'
        release = json.loads(read_url(api + '/releases/tags/v' + VERSION, 1024 * 1024))
        if release.get('tag_name') != 'v' + VERSION or release.get('draft'):
            raise ValueError('Unexpected release metadata')
        assets = [asset for asset in release.get('assets', []) if asset.get('name') == name]
        if len(assets) != 1:
            raise ValueError('Release asset missing or ambiguous')
        asset = assets[0]
        if (type(asset.get('id')) is not int or asset['id'] <= 0
                or type(asset.get('size')) is not int or not 0 < asset['size'] <= limit
                or asset.get('state') != 'uploaded'):
            raise ValueError('Invalid release asset')
        return read_url(api + '/releases/assets/' + str(asset['id']), limit, 'application/octet-stream')


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


def restore_before_removal(home, staged=None, skip=False, fatal=True):
    """Called only after Decky is stopped. Fail before moving/deleting any files.

    A restore that cannot be confirmed blocks uninstall (the plugin would be gone while
    the controller stayed managed) but only warns for install and reinstall: refusing to
    update leaves the user unable to fix anything.
    """
    settings = home / 'settings' / FOLDER
    snapshot = settings / 'recovery.json'
    if not snapshot.exists():
        return
    if snapshot.is_symlink():
        raise ValueError('Refusing symlink recovery snapshot')
    data = json.loads(snapshot.read_text(encoding='utf-8'))
    if not data.get('active'):
        return
    if skip:
        print('WARNING: skipping restoration of the original controller state on request (--skip-restore).')
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
    # Prefer the freshly unpacked code: an installed version can carry a bug that
    # makes recovery impossible, which would otherwise deadlock every reinstall.
    helper_root = staged if (staged is not None and (staged / 'recover.py').is_file()) else target
    if not (helper_root / 'recover.py').is_file():
        raise ValueError('Active recovery snapshot exists but recovery code is missing; files preserved')
    try:
        last_error = None
        for attempt in range(3):
            try:
                result = subprocess.run(['python3', str(helper_root / 'recover.py'), '--settings-dir', str(settings)],
                                        capture_output=True, text=True, timeout=90)
                # A mocked runner may return None; treat that as success, as the
                # previous check=True call did.
                code = getattr(result, 'returncode', 0)
                detail = ((getattr(result, 'stderr', '') or getattr(result, 'stdout', '') or '')).strip()
            except Exception as exc:
                if fatal:
                    raise
                code, detail = 1, '%s: %s' % (type(exc).__name__, exc)
            if code == 0:
                last_error = None
                break
            last_error = detail
            # InputPlumber rebuilds target objects while switching; a short retry
            # covers a transient disappearing object path or a slow read-back.
            time.sleep(1.5)
        if last_error is None and json.loads(snapshot.read_text(encoding='utf-8')).get('active'):
            last_error = 'Recovery did not complete; the snapshot is still marked active.'
        if last_error is not None:
            message = ('Restoring the original controller state failed; files and snapshot preserved. '
                       'Retry the install, or use --skip-restore if the controller must be left as is.\n'
                       + last_error[-800:])
            if fatal:
                raise ValueError(message)
            print('WARNING: ' + message)
            print('WARNING: continuing with the install. The controller may stay managed until it is '
                  're-managed or restored from the retained snapshot.')
    finally:
        # Maintenance restoration is temporary, including a failed update rollback.
        temporary = preference.with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump({'enabled': enabled}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, preference)


def transact(home, action, staged=None, skip_restore=False):
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
        restore_before_removal(home, staged, skip=skip_restore, fatal=(action == 'uninstall'))
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
    parser.add_argument('--skip-restore', action='store_true',
                        help='do not restore the pre-management controller state before replacing or removing files')
    args = parser.parse_args()
    home = validate_home(args.decky_home)
    if os.geteuid() != 0:
        extra = ['--skip-restore'] if args.skip_restore else []
        os.execvp('sudo', ['sudo', 'python3', str(Path(__file__).resolve()), args.action,
                            '--decky-home', str(home), *extra])
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
            transact(home, args.action, staged, skip_restore=args.skip_restore)
    print('MSI Claw A8 Controller Suite: ' + args.action + ' complete. Hardware settings unchanged.')
    print('Preview release: disable/remove the original DeckyPlumber and Back Buttons & Rumble plugins before enabling management. Existing suite button configurations are kept on install/update; clean reinstall/uninstall removes them after recovery.')
    print('IMPORTANT: Save your work and reboot normally before returning to Gaming Mode. Controller detection after a live Decky restart is not reliable on the tested A8.')
    if args.action != 'uninstall':
        print('If rumble or controller behavior remains abnormal after reboot, an EC reset may be needed. It resolved a reported loss of rumble on the tested A8; it is not required for every installation.')
        print('Follow MSI official EC reset guidance: https://www.msi.com/support/technical_details/HH_EC_Reset')


if __name__ == '__main__':
    main()

