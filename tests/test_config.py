import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.config import Store, SuiteError, compile_profile, event, validate_rules


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'config.json'
        self.store = Store(self.path)

    def save(self, scope, rules, enabled=True):
        self.store.save(scope, 'Test', rules, enabled, self.store.data['revision'])

    def test_copies_do_not_link(self):
        self.save('default', {'M1': ['A']})
        self.save('1245620', self.store.data['default'])
        self.save('374320', self.store.data['games']['1245620']['rules'])
        self.save('1245620', {'M1': ['B']})
        self.save('default', {'M1': ['X']})
        self.assertEqual(self.store.selected('374320'), ('374320', {'M1': ['A']}))
        self.assertEqual(Store(self.path).selected('1245620')[1], {'M1': ['B']})

    def test_disable_retains_copy_and_delete_uses_default(self):
        self.save('default', {'M1':['A']})
        self.save('1', {'M1':['B']}, False)
        self.assertEqual(self.store.selected('1')[0], 'default')
        self.assertEqual(self.store.data['games']['1']['rules'], {'M1':['B']})
        self.store.delete('1', self.store.data['revision'])
        self.assertEqual(self.store.selected('1')[0], 'default')

    def test_one_config_per_game(self):
        self.save('1', {'M1':['A']})
        self.save('1', {})
        self.assertEqual(len(self.store.data['games']), 1)
        self.assertEqual(self.store.data['games']['1']['rules'], {})

    def test_copy_is_deep(self):
        rules = {'M1':['A']}
        self.save('1', rules)
        rules['M1'].append('B')
        self.assertEqual(self.store.selected('1')[1], {'M1':['A']})

    def test_stale_save_rejected(self):
        self.save('1', {})
        with self.assertRaisesRegex(SuiteError, 'stale_edit'):
            self.store.save('1', 'Test', {}, True, 0)

    def test_invalid_rules(self):
        for rules in ({'Guide':['A']}, {'M1':['bad']}, {'M1':['A','A']}, {'M1':'A'}, {'target_devices':['ds5']}):
            with self.subTest(rules=rules), self.assertRaises(SuiteError):
                validate_rules(rules)

    def test_failed_disk_write_preserves_in_memory(self):
        before = self.store.snapshot()
        with patch('backend.config.atomic_json', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.save('1', {})
        self.assertEqual(self.store.snapshot(), before)

    def test_corruption_not_overwritten(self):
        self.path.write_text('broken')
        with self.assertRaisesRegex(SuiteError, 'config_corrupt'): Store(self.path)
        self.assertEqual(self.path.read_text(), 'broken')

    def test_legacy_template_key_is_dropped(self):
        legacy = {'schema': 1, 'revision': 2, 'default': {},
                  'games': {'1': {'name': 'Game', 'enabled': True, 'rules': {'M1': ['A']}}},
                  'templates': {'old': {'name': 'Old', 'rules': {'M1': ['B']}}}}
        self.path.write_text(json.dumps(legacy))
        store = Store(self.path)
        self.assertNotIn('templates', store.snapshot())
        self.assertEqual(store.selected('1')[1], {'M1': ['A']})
        # The key disappears from disk on the next commit instead of being rewritten.
        store.delete('1', store.data['revision'])
        self.assertNotIn('templates', json.loads(self.path.read_text()))

    def test_compiler_preserves_base_and_strips_targets(self):
        base = {'version':1,'kind':'DeviceProfile','name':'System','target_devices':['ds5'],
                'description':'preserve', 'mapping':[
                    {'name':'old','source_event':event('M1'),'target_events':[event('B')]},
                    {'name':'guide','source_event':{'gamepad':{'button':'Guide'}},'target_events':[]}]}
        original = copy.deepcopy(base)
        result = compile_profile(base, {'M1':['A','key:KeySpace']})
        self.assertNotIn('target_devices', result)
        self.assertEqual(len(result['mapping']), 2)
        self.assertEqual(result['mapping'][0]['name'], 'guide')
        self.assertEqual(result['description'], 'preserve')
        self.assertEqual(base, original)
