import io
import json
import unittest
from unittest.mock import patch

from backend.updates import check_latest, version_key


class UpdateTests(unittest.TestCase):
    def check(self, current='0.1.5', **release):
        metadata = {'tag_name': 'v0.1.6', 'draft': False, 'prerelease': False, **release}
        with patch('backend.updates.urllib.request.urlopen',
                   return_value=io.BytesIO(json.dumps(metadata).encode())) as request:
            result = check_latest(current)
        self.assertEqual(request.call_args.kwargs['timeout'], 10)
        self.assertTrue(request.call_args.args[0].full_url.endswith('/releases/latest'))
        return result

    def test_numeric_comparison_and_alpha_upgrade(self):
        self.assertTrue(self.check('0.1.9', tag_name='v0.1.10')['available'])
        self.assertTrue(self.check('0.1.6-alpha.33')['available'])
        self.assertFalse(self.check('0.1.6')['available'])
        self.assertFalse(self.check('0.2.0')['available'])
        self.assertEqual(self.check()['latest'], '0.1.6')
        self.assertEqual(self.check()['current'], '0.1.5')

    def test_rejects_nonstable_or_malformed_releases(self):
        for changes in ({'draft': True}, {'prerelease': True}, {'tag_name': 'v0.1.6-alpha.1'},
                        {'tag_name': None}, {'tag_name': '../main'}, {'draft': None}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.check(**changes)
        with self.assertRaises(ValueError):
            version_key('invalid')

    def test_network_errors_and_oversized_response_do_not_report_success(self):
        with patch('backend.updates.urllib.request.urlopen', side_effect=TimeoutError), \
             self.assertRaises(TimeoutError):
            check_latest('0.1.5')
        with patch('backend.updates.urllib.request.urlopen',
                   return_value=io.BytesIO(b' ' * (256 * 1024 + 1))), self.assertRaises(ValueError):
            check_latest('0.1.5')
