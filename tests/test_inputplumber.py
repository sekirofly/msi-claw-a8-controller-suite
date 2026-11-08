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
