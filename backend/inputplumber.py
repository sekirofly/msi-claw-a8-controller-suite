"""Capability-gated D-Bus adapter. No service restarts or positional selection."""
import json
import logging
import subprocess
import time
from .config import SuiteError, atomic_json, compile_profile, BUTTONS
from .defaults import system_defaults

log = logging.getLogger('msi-claw-a8-controller-suite')

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
    def __init__(self, hardware, settings_path, bus=None):
        self.hardware, self.bus = hardware, bus or Bus()
        self.preference_path = settings_path.with_name('management.json')
        if self.preference_path.exists():
            preference = json.loads(self.preference_path.read_text(encoding='utf-8'))
        else:
            # One-time migration of the old choice only. Never use its captured
            # profile/targets; leave recovery.json untouched as a legacy backup.
            legacy = settings_path.with_name('recovery.json')
            try:
                old = json.loads(legacy.read_text()) if legacy.exists() else {}
            except (ValueError, OSError):
                old = {}
            preference = {'enabled': old.get('active', True) if isinstance(old, dict) else True}
        if not isinstance(preference, dict) or type(preference.get('enabled')) is not bool:
            raise SuiteError('config_corrupt')
        self.enabled = preference['enabled']
        self.restore_pending = preference.get('restore_pending', not self.enabled)
        if type(self.restore_pending) is not bool:
            raise SuiteError('config_corrupt')
        self.persist_preference()
        self.ready = False
        self.identity = None
        self.expected_targets = None
        self.expected_profile = None

    def persist_preference(self):
        atomic_json(self.preference_path, {'enabled': self.enabled, 'restore_pending': self.restore_pending})

    def set_enabled(self, enabled):
        atomic_json(self.preference_path, {'enabled': enabled, 'restore_pending': not enabled})
        self.enabled, self.restore_pending, self.ready = enabled, not enabled, False

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
        # Retry a complete read when objects vanish during a rebuild. A partial
        # list must never become the original snapshot or confirm restoration.
        for attempt in range(3):
            try:
                paths = self.bus.property(path, IFACE, 'TargetDevices')
                return sorted(self.bus.property(target, 'org.shadowblip.Input.Target', 'DeviceType')
                              for target in paths)
            except SuiteError:
                if attempt == 2:
                    raise
                time.sleep(.1)

    def status(self):
        path, identity = self.discover()
        profile = self.profile(path)
        capabilities = self.bus.property(path, IFACE, 'Capabilities')
        return {'path': path, 'identity': identity, 'targets': self.targets(path),
                'profile': profile.get('name', ''), 'capabilities': capabilities,
                'sources': [key for key, value in BUTTONS.items()
                            if 'Gamepad:Button:' + value in capabilities]}

    def set_targets(self, path, values, confirm=True, timeout=10.0):
        """Set the target set; confirm reads it back when the caller needs proof.

        Calling SetTargetDevices makes InputPlumber tear down and rebuild every
        target object, so it is never called for a set that is already in place:
        an unnecessary call starts a rebuild whose transient state makes the
        read-back fail, and a retry then restarts that rebuild again.
        """
        wanted = sorted(values)
        if self.targets(path) == wanted:
            return True
        self.bus.call(path, IFACE, 'SetTargetDevices', 'as', len(values), *values)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if self.targets(path) == wanted:
                    return True
            except SuiteError:
                pass  # Rebuilding objects are not a confirmed target set.
            time.sleep(.1)
        actual = self.targets(path)
        log.warning('SetTargetDevices wanted %s, read back %s', wanted, actual)
        if confirm:
            raise SuiteError('readback_failed')
        return False

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

    def checked_device(self):
        path, identity = self.discover()
        if self.identity is not None and identity != self.identity:
            raise SuiteError('device_changed')
        self.identity = identity
        return path

    def reconcile(self, rules):
        if not self.enabled:
            if self.restore_pending:
                self.restore()
            return
        path = self.checked_device()
        base, defaults = system_defaults()
        gamepads = {'xb360', 'gamepad', 'xbox-series', 'xbox-elite', 'ds5', 'ds5-edge',
                    'deck', 'deck-uhid', 'hori-steam', '8bitdo-u2', 'steam-deck'}
        if len([t for t in defaults if t in gamepads]) != 1:
            raise SuiteError('unknown_targets')
        targets = sorted([t for t in defaults if t not in gamepads] + ['xbox-elite'])
        supported = self.bus.property(ROOT + '/Manager', 'org.shadowblip.InputManager', 'SupportedTargetDeviceIds')
        if 'xbox-elite' not in supported:
            raise SuiteError('elite_unavailable')
        if any(t not in supported for t in targets):
            raise SuiteError('unknown_targets')
        capabilities = self.bus.property(path, IFACE, 'Capabilities')
        if any('Gamepad:Button:' + BUTTONS[key] not in capabilities for key in rules):
            raise SuiteError('source_unavailable')
        desired = compile_profile(base, rules)
        actual, current = self.profile(path), self.targets(path)
        # While running, do not fight an unrelated manager. A real system reset
        # is recognizable without any historical snapshot.
        if self.ready and not (current == self.expected_targets and canonical(actual) == canonical(self.expected_profile)):
            if not (current == defaults and canonical(actual.get('mapping', [])) == canonical(base['mapping'])):
                raise SuiteError('external_change')
        self.set_targets(path, targets)
        if canonical(actual) != canonical(desired):
            actual = self.load(path, desired)
        if self.targets(path) != targets:
            raise SuiteError('readback_failed')
        self.expected_targets, self.expected_profile, self.ready = targets, actual, True

    def restore(self):
        """Apply installed system defaults, even when no legacy snapshot exists."""
        path = self.checked_device()
        profile, targets = system_defaults()
        supported = self.bus.property(ROOT + '/Manager', 'org.shadowblip.InputManager', 'SupportedTargetDeviceIds')
        if any(t not in supported for t in targets):
            raise SuiteError('unknown_targets')
        self.set_targets(path, targets)
        self.load(path, profile)
        if self.targets(path) != targets:
            raise SuiteError('readback_failed')
        self.restore_pending = False
        self.persist_preference()
        self.ready = False
        self.expected_targets = self.expected_profile = None


def canonical(value):
    # Ignore null/default empty fields inserted by serde, but preserve false/zero.
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [canonical(v) for v in value]
    return value
