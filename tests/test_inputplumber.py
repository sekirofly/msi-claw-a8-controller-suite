import copy
import tempfile
import unittest
from pathlib import Path
from backend.inputplumber import InputPlumber, IFACE
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
        if name=='SupportedTargetDeviceIds': return ['xbox-elite']
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
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'recovery.json'
        self.bus=Bus();self.ip=InputPlumber(Hardware(),self.path,self.bus)

    def reboot(self):
        self.ip = InputPlumber(Hardware(), self.path, self.bus)

    def test_first_install_and_reboot_auto_enable(self):
        original = copy.deepcopy(self.bus.profile)
        targets = list(self.bus.target)
        self.assertTrue(self.ip.enabled)
        self.ip.reconcile({'M1': ['A']})
        self.assertIn('xbox-elite', self.bus.target)
        self.bus.profile, self.bus.target = original, targets
        self.reboot()
        self.ip.reconcile({'M1': ['A']})
        self.assertIn('xbox-elite', self.bus.target)
        self.assertEqual(self.bus.profile['mapping'][0]['name'], 'M1')
        self.assertEqual(self.ip.snapshot['original_profile'], original)

    def test_session_reset_without_backend_restart(self):
        original, targets = copy.deepcopy(self.bus.profile), list(self.bus.target)
        self.ip.reconcile({'M2': ['B']})
        self.bus.profile, self.bus.target = original, sorted(targets)
        self.ip.reconcile({'M2': ['B']})
        self.assertIn('xbox-elite', self.bus.target)
        self.assertEqual(self.bus.profile['mapping'][0]['name'], 'M2')

    def test_disabled_survives_reboot_and_reenable_preserves_first_snapshot(self):
        original = copy.deepcopy(self.bus.profile)
        self.ip.reconcile({'M1': ['A']})
        self.ip.set_enabled(False)
        self.ip.reconcile({})
        self.reboot()
        self.bus.calls.clear()
        self.ip.reconcile({})
        self.assertFalse(self.ip.enabled)
        self.assertEqual(self.bus.calls, [])
        self.bus.profile['name'] = 'Changed while disabled'
        self.ip.set_enabled(True)
        self.ip.reconcile({})
        self.assertEqual(self.ip.snapshot['original_profile'], original)
        self.ip.set_enabled(False)
        self.ip.reconcile({})
        self.assertEqual(self.bus.profile, original)

    def test_disable_before_first_device_is_available(self):
        self.ip.set_enabled(False)
        self.reboot()
        self.ip.reconcile({})
        self.assertEqual(self.bus.calls, [])
        self.assertIsNone(self.ip.snapshot)

    def test_failed_restore_never_reenables_after_reboot(self):
        self.ip.reconcile({})
        self.ip.set_enabled(False)
        self.bus.fail = True
        with self.assertRaises(RuntimeError):
            self.ip.reconcile({})
        self.reboot()
        self.assertFalse(self.ip.enabled)
        self.assertTrue(self.ip.snapshot['active'])
        self.bus.fail = False
        self.ip.reconcile({})
        self.assertNotIn('xbox-elite', self.bus.target)
        self.assertFalse(self.ip.snapshot['active'])

    def test_legacy_paused_snapshot_recovers_without_restore_button(self):
        self.ip.enable()
        self.ip.snapshot['paused'] = True
        self.ip.persist()
        self.ip.preference_path.unlink()
        self.reboot()
        self.ip.reconcile({})
        self.assertTrue(self.ip.enabled)
        self.assertFalse(self.ip.snapshot['paused'])

    def test_legacy_explicit_stop_stays_disabled(self):
        self.ip.enable()
        self.ip.restore()
        self.ip.preference_path.unlink()
        self.reboot()
        self.assertFalse(self.ip.enabled)

    def test_repeated_reconcile_does_not_recreate_output(self):
        self.ip.reconcile({'M1': ['A']})
        self.bus.calls.clear()
        self.ip.reconcile({'M1': ['A']})
        self.assertTrue(all(name == 'GetProfileYaml' for _, name in self.bus.calls))

    def test_late_device_recovers_automatically(self):
        paths = self.bus.paths
        self.bus.paths = lambda: []
        with self.assertRaisesRegex(SuiteError, 'composite_ambiguous'):
            self.ip.reconcile({})
        self.assertFalse(self.path.exists())
        self.bus.paths = paths
        self.ip.reconcile({})
        self.assertIn('xbox-elite', self.bus.target)

    def test_different_identity_never_replaces_original_snapshot(self):
        self.ip.reconcile({})
        original = self.path.read_bytes()
        self.reboot()
        self.ip.hardware.discover = lambda: {'usb': 'different'}
        self.bus.calls.clear()
        with self.assertRaisesRegex(SuiteError, 'device_changed'):
            self.ip.reconcile({})
        self.assertEqual(self.path.read_bytes(), original)
        self.assertTrue(all(name == 'GetProfileYaml' for _, name in self.bus.calls))

    def test_external_change_requires_retry_not_restore(self):
        self.ip.reconcile({})
        self.bus.profile['name'] = 'External'
        with self.assertRaisesRegex(SuiteError, 'external_change'):
            self.ip.reconcile({})
        self.ip.ready = False  # Explicit retry of the existing enabled choice.
        self.ip.reconcile({})
        self.assertEqual(self.bus.profile['name'], 'MSI Claw A8 Controller Suite')

    def test_targets_only_selected_embedded(self):
        self.ip.enable();self.ip.apply({'M1':['A']})
        self.assertTrue(all(p=='/compositeA8' for p,name in self.bus.calls))
        self.assertIn('keyboard',self.bus.target)
        self.assertIn('mouse',self.bus.target)

    def test_read_does_not_write(self):
        self.ip.status()
        self.assertTrue(all(name=='GetProfileYaml' for _,name in self.bus.calls))
        self.assertFalse(self.path.exists())

    def test_restore_original_not_hardware(self):
        original=copy.deepcopy(self.bus.profile)
        self.ip.enable();self.ip.apply({'M1':['A']});self.ip.restore()
        self.assertEqual(self.bus.profile,original)
        self.assertEqual(self.bus.target,sorted(['xbox-series','keyboard','mouse']))
        self.assertFalse(self.ip.snapshot['active'])

    def test_external_change_pauses_without_overwrite(self):
        self.ip.enable();self.bus.profile['name']='External'
        with self.assertRaisesRegex(SuiteError,'external_change'):self.ip.apply({})
        self.assertEqual(self.bus.profile['name'],'External')
        self.assertTrue(self.ip.snapshot['paused'])

    def test_snapshot_durable_before_target_failure(self):
        self.bus.fail=True
        with self.assertRaises(RuntimeError):self.ip.enable()
        self.assertTrue(self.path.exists())
        self.assertTrue(self.ip.snapshot['paused'])

    def test_ambiguous_composite_never_writes(self):
        self.bus.paths=lambda:['/compositeA8','/compositeA8']
        with self.assertRaisesRegex(SuiteError,'composite_ambiguous'):self.ip.enable()
        self.assertEqual(self.bus.calls,[])

    def test_mappings_do_not_recreate_targets(self):
        self.ip.enable();self.bus.calls=[]
        self.ip.apply({'M1':['A']});self.ip.apply({'M1':['B']})
        self.assertFalse(any(name=='SetTargetDevices' for _,name in self.bus.calls))
