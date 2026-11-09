"""Capability-gated D-Bus adapter. No service restarts or positional selection."""
import copy
import json
import subprocess
import time
from .config import SuiteError, atomic_json, compile_profile, BUTTONS

SERVICE = 'org.shadowblip.InputPlumber'
IFACE = 'org.shadowblip.Input.CompositeDevice'
ROOT = '/org/shadowblip/InputPlumber'


def yaml_module():
    try:
        import yaml
        return yaml
    except ImportError as exc:
        raise SuiteError('yaml_missing') from exc


class Bus:
    def run(self, *args):
        # busctl exits non-zero when an object path disappears mid-transition,
        # which happens while InputPlumber rebuilds its target devices. Report
        # it as a SuiteError so callers can retry instead of dying on a
        # CalledProcessError traceback.
        try:
            result = subprocess.run(['busctl', '--system', '--timeout=3', '--json=short', *args],
                                    capture_output=True, text=True, timeout=5, check=True)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            raise SuiteError('interface_unavailable') from exc
        return json.loads(result.stdout) if result.stdout.strip() else None

    def property(self, path, interface, name):
        return self.run('get-property', SERVICE, path, interface, name)['data']

    def call(self, path, interface, name, signature=None, *args):
        tail = [signature, *map(str, args)] if signature else []
        result = self.run('call', SERVICE, path, interface, name, *tail)
        return result['data'][0] if result and result.get('data') else None

    def paths(self):
        result = subprocess.run(['busctl', '--system', '--timeout=3', '--list', 'tree', SERVICE],
                                capture_output=True, text=True, timeout=5, check=True)
        return [s.strip() for s in result.stdout.splitlines()
                if s.strip().startswith(ROOT + '/CompositeDevice') and '/' not in s.strip()[len(ROOT)+1:]]


class InputPlumber:
    def __init__(self, hardware, snapshot_path, bus=None):
        self.hardware, self.path, self.bus = hardware, snapshot_path, bus or Bus()
        self.snapshot = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else None
        self.preference_path = self.path.with_name('management.json')
        if self.preference_path.exists():
            preference = json.loads(self.preference_path.read_text(encoding='utf-8'))
            if type(preference.get('enabled')) is not bool:
                raise SuiteError('config_corrupt')
            self.enabled = preference['enabled']
        else:
            # Migrate an explicit legacy stop; an active/paused snapshot stays enabled.
            self.enabled = bool(self.snapshot.get('active')) if self.snapshot else True
            self.set_enabled(self.enabled)
        self.ready = False

    def set_enabled(self, enabled):
        atomic_json(self.preference_path, {'enabled': enabled})
        self.enabled = enabled

    def discover(self):
        identity = self.hardware.discover()
        matches = []
        for path in self.bus.paths():
            sources = self.bus.property(path, IFACE, 'SourceDevicePaths')
            if any(self.hardware.matches_source(s, identity) for s in sources):
                # Reject composites that also contain any unrelated gamepad source.
                for source in sources:
                    if source.startswith('/dev/') and not self.hardware.matches_source(source, identity):
                        name = source.rsplit('/', 1)[-1]
                        if name.startswith('event'):
                            phys = self.hardware.sys / 'class/input' / name / 'device/phys'
                            # A8's platform hotkeys only; do not silently include an
                            # external keyboard/gamepad in a shared composite.
                            if not phys.is_file() or phys.read_text().strip() not in ('isa0060/serio0/input0', 'wmi/input0'):
                                raise SuiteError('mixed_device')
                        elif name.startswith('iio:device'):
                            imu = (self.hardware.sys / 'bus/iio/devices' / name).resolve()
                            if '/usb' in imu.as_posix() or not (imu / 'name').is_file():
                                raise SuiteError('mixed_device')
                            if (imu / 'name').read_text().strip() not in ('gyro_3d', 'accel_3d'):
                                raise SuiteError('mixed_device')
                        else:
                            raise SuiteError('mixed_device')
                matches.append(path)
        if len(matches) != 1:
            raise SuiteError('composite_ambiguous')
        return matches[0], identity['usb']

    def profile(self, path):
        raw = self.bus.call(path, IFACE, 'GetProfileYaml')
        profile = yaml_module().safe_load(raw)
        if not isinstance(profile, dict) or profile.get('kind') != 'DeviceProfile' or not isinstance(profile.get('mapping', []), list):
            raise SuiteError('profile_unreadable')
        return profile

    def targets(self, path):
        # A target object can vanish between listing and reading its type while
        # InputPlumber rebuilds devices; skip it and let the caller retry rather
        # than failing the whole read (and with it a restore or an install).
        result = []
        for target in self.bus.property(path, IFACE, 'TargetDevices'):
            try:
                result.append(self.bus.property(target, 'org.shadowblip.Input.Target', 'DeviceType'))
            except SuiteError:
                continue
        return sorted(result)

    def status(self):
        path, identity = self.discover()
        profile = self.profile(path)
        capabilities = self.bus.property(path, IFACE, 'Capabilities')
        return {'path': path, 'identity': identity, 'targets': self.targets(path),
                'profile': profile.get('name', ''), 'capabilities': capabilities,
                'sources': [key for key, value in BUTTONS.items()
                            if 'Gamepad:Button:' + value in capabilities]}

    def set_targets(self, path, values):
        self.bus.call(path, IFACE, 'SetTargetDevices', 'as', len(values), *values)
        for _ in range(20):
            if self.targets(path) == sorted(values):
                return
            time.sleep(.1)
        raise SuiteError('readback_failed')

    def load(self, path, profile):
        self.bus.call(path, IFACE, 'LoadProfileFromYaml', 's', json.dumps(profile))
        # Serde can add defaults and strip unknown fields: compare the applied mapping,
        # not a requested name alone. Unknown mismatches fail closed.
        for _ in range(15):
            actual = self.profile(path)
            if canonical(actual.get('mapping', [])) == canonical(profile.get('mapping', [])):
                return actual
            time.sleep(.1)
        raise SuiteError('readback_failed')

    def persist(self):
        atomic_json(self.path, self.snapshot)

    def enable(self):
        path, identity = self.discover()
        base = self.profile(path)
        original = self.targets(path)
        supported = self.bus.property(ROOT + '/Manager', 'org.shadowblip.InputManager', 'SupportedTargetDeviceIds')
        if 'xbox-elite' not in supported:
            raise SuiteError('elite_unavailable')
        allowed = {'xb360', 'gamepad', 'xbox-series', 'xbox-elite', 'ds5', 'ds5-edge', 'deck', 'deck-uhid', 'hori-steam', '8bitdo-u2'}
        games = [x for x in original if x in allowed]
        if len(games) != 1 or any(x not in allowed | {'keyboard', 'mouse', 'dbus', 'touchscreen', 'touchpad'} for x in original):
            raise SuiteError('unknown_targets')
        expected = sorted([x for x in original if x not in allowed] + ['xbox-elite'])
        if self.snapshot:
            if identity != self.snapshot['identity']:
                raise SuiteError('device_changed')
            # Never replace the first pre-management profile, even after a stop/reboot.
            expected = self.snapshot['targets']
            self.snapshot.update(active=True, paused=False, pending=True, expected_profile=base, error=None)
        else:
            self.snapshot = {'active': True, 'identity': identity, 'original_profile': base,
                             'original_targets': original, 'targets': expected, 'expected_profile': base,
                             'paused': False, 'pending': True}
        self.persist()  # Durable recovery before first mutation.
        try:
            if expected != original:
                self.set_targets(path, expected)
            self.snapshot['pending'] = False
            self.persist()
            self.ready = True
        except Exception as exc:
            self.snapshot['paused'] = True
            self.snapshot['error'] = str(exc) if isinstance(exc, SuiteError) else 'operation_failed'
            self.persist()
            raise

    def reconcile(self, rules):
        if not self.enabled:
            self.restore()
            return
        if not self.ready:
            self.enable()
        else:
            try:
                path, identity = self.discover()
            except Exception:
                self.ready = False  # A re-enumerated device needs a fresh activation.
                raise
            if identity != self.snapshot['identity']:
                raise SuiteError('device_changed')
            # InputPlumber recreates the original output after boot/session changes.
            # Recognize that reset; unrelated live changes still fail closed in apply().
            original = copy.deepcopy(self.snapshot['original_profile'])
            original.pop('target_devices', None)
            actual = self.profile(path)
            actual.pop('target_devices', None)
            if (self.targets(path) == self.snapshot['original_targets']
                    and canonical(actual) == canonical(original)):
                self.enable()
        self.apply(rules)

    def apply(self, rules):
        snap = self.snapshot
        if not snap or not snap.get('active'):
            raise SuiteError('management_disabled')
        if snap.get('paused'):
            raise SuiteError(snap.get('error') or 'management_disabled')
        path, identity = self.discover()
        if identity != snap['identity']:
            raise SuiteError('device_changed')
        actual = self.profile(path)
        if self.targets(path) != snap['targets'] or canonical(actual) != canonical(snap['expected_profile']):
            snap['paused'] = True
            snap['error'] = 'external_change'
            self.persist()
            raise SuiteError('external_change')
        desired = compile_profile(snap['original_profile'], rules)
        if canonical(actual) == canonical(desired):
            return
        # Only sources advertised by the selected embedded composite may be remapped.
        capabilities = self.bus.property(path, IFACE, 'Capabilities')
        if any('Gamepad:Button:' + BUTTONS[key] not in capabilities for key in rules):
            raise SuiteError('source_unavailable')
        try:
            actual = self.load(path, desired)
            if self.targets(path) != snap['targets']:
                raise SuiteError('external_change')
            snap['expected_profile'] = actual
            self.persist()
        except Exception as exc:
            snap['paused'] = True
            snap['error'] = str(exc) if isinstance(exc, SuiteError) else 'operation_failed'
            self.persist()
            raise

    def restore(self):
        if not self.snapshot or not self.snapshot.get('active'):
            return
        path, identity = self.discover()
        snap = self.snapshot
        if identity != snap['identity']:
            raise SuiteError('device_changed')
        # Explicit user restore, not an automatic overwrite of someone else's state.
        original = copy.deepcopy(snap['original_profile'])
        original.pop('target_devices', None)
        self.set_targets(path, snap['original_targets'])
        self.load(path, original)
        if self.targets(path) != snap['original_targets']:
            raise SuiteError('readback_failed')
        snap['active'] = False
        snap['paused'] = False
        self.persist()
        self.ready = False


def canonical(value):
    # Ignore null/default empty fields inserted by serde, but preserve false/zero.
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [canonical(v) for v in value]
    return value
