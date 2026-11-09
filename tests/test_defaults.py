import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from backend.defaults import system_defaults, DEVICE_FILE
from backend.config import SuiteError


class DefaultTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'profiles').mkdir(); (self.root / 'devices').mkdir()
        self.profile = {'version':1,'kind':'DeviceProfile','name':'Default','mapping':[
            {'name':'system mapping','source_event':{'gamepad':{'button':'QuickAccess2'}},
             'target_events':[{'gamepad':{'button':'Screenshot'}}]}]}
        self.device = {'kind':'CompositeDevice', 'matches':[{'dmi_data':{
            'board_name':'MS-1T8K', 'board_vendor':'Micro-Star International Co., Ltd.'}}],
            'target_devices':['xbox-series','keyboard','mouse']}
        self.write()
        mock = patch('backend.defaults.DATA_DIRS', (self.root,)); mock.start(); self.addCleanup(mock.stop)

    def write(self):
        (self.root/'profiles/default.yaml').write_text(json.dumps(self.profile))
        (self.root/'devices'/DEVICE_FILE).write_text(json.dumps(self.device))

    def test_loads_installed_profile_and_targets(self):
        profile, targets = system_defaults()
        self.assertEqual(profile, self.profile)
        self.assertEqual(targets, sorted(self.device['target_devices']))

    def test_profile_target_override_takes_precedence_without_implicit_rebuild(self):
        self.profile['target_devices'] = ['hori-steam','keyboard']
        self.write()
        profile, targets = system_defaults()
        self.assertEqual(targets, ['hori-steam','keyboard'])
        self.assertNotIn('target_devices', profile)

    def test_missing_or_wrong_device_fails_without_guessing(self):
        self.device['matches'] = [{'dmi_data':{'board_name':'OTHER'}}]; self.write()
        with self.assertRaisesRegex(SuiteError,'system_defaults_unavailable'): system_defaults()
        (self.root/'devices'/DEVICE_FILE).unlink()
        with self.assertRaisesRegex(SuiteError,'system_defaults_unavailable'): system_defaults()

    def test_invalid_profile_or_targets_rejected(self):
        for targets in ('xbox-series', [], ['keyboard','keyboard']):
            self.device['target_devices'] = targets; self.write()
            with self.assertRaisesRegex(SuiteError,'system_defaults_unavailable'): system_defaults()
        (self.root/'profiles/default.yaml').write_text('not: [valid')
        with self.assertRaisesRegex(SuiteError,'system_defaults_unavailable'): system_defaults()
