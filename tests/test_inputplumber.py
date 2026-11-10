import copy
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.inputplumber import InputPlumber
from backend.inputplumber import Bus as PlumberBus
from backend.config import SuiteError, BUTTONS


class Hardware:
    def discover(self): return {'usb':'internal'}
    def matches_source(self, source, identity): return source == '/dev/input/event7'


class Bus:
    def __init__(self):
        self.profile={'kind':'DeviceProfile','version':1,'name':'Original','mapping':[]}
        self.target=['xbox-series','keyboard','mouse']
        self.calls=[]
        self.fail=False
    def paths(self): return ['/compositeExternal','/compositeA8']
    def property(self,path,interface,name):
        if name=='SourceDevicePaths': return ['/dev/input/event7'] if path=='/compositeA8' else []
        if name=='TargetDevices': return self.target
        if name=='DeviceType': return path
        if name=='SupportedTargetDeviceIds': return ['xbox-elite','xbox-series','keyboard','mouse']
        if name=='Capabilities': return ['Gamepad:Button:'+x for x in BUTTONS.values()]
        raise AssertionError(name)
    def call(self,path,interface,name,signature=None,*args):
        self.calls.append((path,name))
        if name=='GetProfileYaml':
            import json
            return json.dumps(self.profile)
        if self.fail: raise RuntimeError('failure')
        if name=='SetTargetDevices': self.target=sorted(args[1:])
        if name=='LoadProfileFromYaml':
            import json
            self.profile=json.loads(args[0])


class InputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'management.json'
        self.base = {'kind': 'DeviceProfile', 'version': 1, 'name': 'Default', 'mapping': []}
        self.defaults = ['keyboard', 'mouse', 'xbox-series']
        mock = patch('backend.inputplumber.system_defaults', side_effect=lambda: (copy.deepcopy(self.base), list(self.defaults)))
        mock.start(); self.addCleanup(mock.stop)
        self.bus = Bus()
        self.reboot()

    def reboot(self):
        self.ip = InputPlumber(Hardware(), self.path, self.bus)

    def test_first_install_and_reboot_apply_without_snapshot(self):
        self.ip.reconcile({'M1': ['A']})
        self.assertIn('xbox-elite', self.bus.target)
        self.assertFalse(self.path.with_name('recovery.json').exists())
        self.bus.profile = copy.deepcopy(self.base)
        self.bus.target = list(self.defaults)
        self.reboot()
        self.ip.reconcile({'M2': ['B']})
        self.assertEqual(self.bus.profile['mapping'][0]['name'], 'M2')
        self.assertIn('xbox-elite', self.bus.target)

    def test_disabled_reboot_does_not_touch_device(self):
        self.ip.reconcile({'M1': ['A']})
        self.ip.set_enabled(False)
        self.ip.reconcile({})
        self.assertEqual(self.bus.profile, self.base)
        self.assertEqual(sorted(self.bus.target), self.defaults)
        self.reboot()
        self.bus.calls.clear()
        self.ip.reconcile({})
        self.assertFalse(self.ip.enabled)
        self.assertEqual(self.bus.calls, [])
        self.ip.set_enabled(True)
        self.ip.reconcile({'M1': ['B']})
        self.assertIn('xbox-elite', self.bus.target)

    def test_failed_restore_remains_disabled_and_retries_after_reboot(self):
        self.ip.reconcile({})
        self.ip.set_enabled(False)
        self.bus.fail = True
        with self.assertRaises(RuntimeError): self.ip.reconcile({})
        self.reboot()
        self.assertFalse(self.ip.enabled)
        self.assertTrue(self.ip.restore_pending)
        self.bus.fail = False
        self.ip.reconcile({})
        self.assertEqual(sorted(self.bus.target), self.defaults)
        self.assertFalse(self.ip.restore_pending)

    def test_legacy_snapshot_is_preserved_but_never_used(self):
        legacy = self.path.with_name('recovery.json')
        legacy.write_text('{"active":true,"original_profile":{"name":"bad"},"original_targets":["bad"]}')
        original = legacy.read_bytes()
        self.reboot()
        self.ip.reconcile({'M1':['A']})
        self.ip.set_enabled(False)
        self.ip.reconcile({})
        self.assertEqual(self.bus.profile, self.base)
        self.assertEqual(legacy.read_bytes(), original)

    def test_corrupt_legacy_snapshot_does_not_block_management(self):
        self.path.with_name('recovery.json').write_text('invalid')
        self.reboot()
        self.ip.reconcile({})
        self.assertTrue(self.ip.ready)

    def test_legacy_disabled_preference_migrates_and_restores_once(self):
        self.path.write_text('{"enabled":false}')
        self.reboot()
        self.ip.reconcile({})
        self.assertFalse(self.ip.enabled)
        self.assertFalse(self.ip.restore_pending)
        self.reboot()
        self.bus.calls.clear()
        self.ip.reconcile({})
        self.assertEqual(self.bus.calls, [])

    def test_legacy_choice_without_preference_is_migrated(self):
        self.path.unlink()
        self.path.with_name('recovery.json').write_text('{"active":false}')
        self.reboot()
        self.assertFalse(self.ip.enabled)

    def test_no_snapshot_needed_for_restore_and_system_updates_are_used(self):
        self.ip.set_enabled(False)
        self.base['name'] = 'Updated system default'
        self.ip.restore()
        self.assertEqual(self.bus.profile, self.base)
        self.assertEqual(sorted(self.bus.target), self.defaults)

    def test_missing_defaults_prevents_all_device_writes(self):
        with patch('backend.inputplumber.system_defaults', side_effect=SuiteError('system_defaults_unavailable')):
            with self.assertRaisesRegex(SuiteError, 'system_defaults_unavailable'): self.ip.reconcile({})
            self.ip.set_enabled(False)
            with self.assertRaisesRegex(SuiteError, 'system_defaults_unavailable'): self.ip.restore()
        self.assertEqual(self.bus.calls, [])
        self.assertTrue(self.ip.restore_pending)

    def test_unsupported_restore_targets_do_not_mutate(self):
        self.defaults.append('unsupported')
        with self.assertRaisesRegex(SuiteError,'unknown_targets'): self.ip.restore()
        self.assertEqual(self.bus.calls, [])

    def test_repeated_mapping_does_not_recreate_targets(self):
        self.ip.reconcile({'M1': ['A']})
        self.bus.calls.clear()
        self.ip.reconcile({'M1': ['B']})
        self.ip.reconcile({'M1': ['B']})
        self.assertFalse(any(name == 'SetTargetDevices' for _, name in self.bus.calls))
        self.assertTrue(all(path == '/compositeA8' for path, _ in self.bus.calls))

    def test_external_change_requires_explicit_retry(self):
        self.ip.reconcile({})
        self.bus.profile['name'] = 'External'
        with self.assertRaisesRegex(SuiteError, 'external_change'): self.ip.reconcile({})
        self.ip.set_enabled(True)
        self.ip.reconcile({})
        self.assertEqual(self.bus.profile['name'], 'MSI Claw A8 Controller Suite')

    def test_system_reset_is_reapplied(self):
        self.ip.reconcile({})
        self.bus.profile = copy.deepcopy(self.base)
        self.bus.target = list(self.defaults)
        self.ip.reconcile({'M1': ['A']})
        self.assertIn('xbox-elite', self.bus.target)

    def test_ambiguous_composite_never_writes(self):
        self.bus.paths = lambda: ['/compositeA8', '/compositeA8']
        with self.assertRaisesRegex(SuiteError, 'composite_ambiguous'): self.ip.reconcile({})
        self.assertEqual(self.bus.calls, [])

    def test_changed_identity_does_not_mutate(self):
        self.ip.reconcile({})
        self.ip.hardware.discover = lambda: {'usb':'different'}
        self.bus.calls.clear()
        with self.assertRaisesRegex(SuiteError,'device_changed'): self.ip.restore()
        self.assertEqual(self.bus.calls, [])

    def test_disappearing_target_cannot_confirm_partial_read(self):
        original = self.bus.property
        def property_(path, interface, name):
            if name == 'DeviceType' and path == 'mouse': raise SuiteError('interface_unavailable')
            return original(path, interface, name)
        self.bus.property = property_
        with self.assertRaisesRegex(SuiteError,'interface_unavailable'): self.ip.reconcile({})
        self.assertFalse(any(name != 'GetProfileYaml' for _, name in self.bus.calls))

    def test_transient_target_read_retries(self):
        original = self.bus.property
        reads = []
        def property_(path, interface, name):
            if name == 'TargetDevices': reads.append(True)
            if name == 'DeviceType' and len(reads) == 1: raise SuiteError('interface_unavailable')
            return original(path, interface, name)
        self.bus.property = property_
        with patch('backend.inputplumber.time.sleep'):
            self.assertEqual(self.ip.targets('/compositeA8'), sorted(self.bus.target))
        self.assertEqual(len(reads), 2)

    def test_busctl_failure_becomes_suite_error(self):
        for error in (subprocess.CalledProcessError(1, ['busctl']), subprocess.TimeoutExpired('busctl', 5)):
            with patch('backend.inputplumber.subprocess.run', side_effect=error):
                with self.assertRaisesRegex(SuiteError, 'interface_unavailable'):
                    PlumberBus().run('get-property', 'x')
