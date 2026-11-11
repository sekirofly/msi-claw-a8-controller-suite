import json
import subprocess
import unittest
from unittest.mock import patch

from backend.updates import LIMIT, REPO, UpdateCheckError, check_latest, version_key


def response(body, code=0):
    return subprocess.CompletedProcess([], code, body, b'')


class UpdateTests(unittest.TestCase):
    def check(self, current='0.1.5', **release):
        metadata = {'tag_name': 'v0.1.6', 'draft': False, 'prerelease': False, **release}
        payload = json.dumps(metadata).encode() + b'\n200'
        with patch('backend.updates.subprocess.run', side_effect=[response(payload), response(b'', 28)]) as request:
            result = check_latest(current)
        command = request.call_args.args[0]
        self.assertEqual(command[0], '/usr/bin/curl')
        self.assertIn('--max-time', command)
        self.assertIn('--max-filesize', command)
        self.assertEqual(request.call_args.kwargs['timeout'], 12)
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
            with self.subTest(changes=changes), self.assertRaises(UpdateCheckError):
                self.check(**changes)
        with self.assertRaises(ValueError):
            version_key('invalid')

    def test_api_http_limit_falls_back_to_official_stable_redirect(self):
        with patch('backend.updates.subprocess.run', side_effect=[
                response(b'\n403', 22), response(b'200\n' + (REPO + '/releases/tag/v0.1.7').encode())]) as request:
            result = check_latest('0.1.6')
        self.assertEqual(result, {'current': '0.1.6', 'latest': '0.1.7', 'available': True})
        self.assertEqual(request.call_count, 2)
        fallback = request.call_args.args[0]
        self.assertIn('--head', fallback)
        self.assertEqual(fallback[-1], REPO + '/releases/latest')

    def test_preserves_safe_failure_codes_for_both_channels(self):
        with patch('backend.updates.subprocess.run', side_effect=[response(b'', 60), response(b'', 28)]):
            with self.assertRaises(UpdateCheckError) as error:
                check_latest('0.1.6')
        self.assertEqual(error.exception.failures, {'api': 'tls_certificate', 'fallback': 'timeout'})
        with patch('backend.updates.subprocess.run', side_effect=FileNotFoundError):
            with self.assertRaises(UpdateCheckError) as error:
                check_latest('0.1.6')
        self.assertEqual(error.exception.failures, {'api': 'curl_missing', 'fallback': 'curl_missing'})

    def test_fallback_rejects_external_urls_prereleases_and_wrong_repositories(self):
        for url in ('https://example.com/releases/tag/v0.1.7', REPO + '/releases/tag/v0.1.7-alpha.1',
                    'https://github.com/other/repo/releases/tag/v0.1.7'):
            with self.subTest(url=url), patch('backend.updates.subprocess.run', side_effect=[
                    response(b'', 28), response(('200\n' + url).encode())]):
                with self.assertRaises(UpdateCheckError):
                    check_latest('0.1.6')

    def test_timeout_and_oversized_response_do_not_report_success(self):
        with patch('backend.updates.subprocess.run', side_effect=subprocess.TimeoutExpired('curl', 12)):
            with self.assertRaises(UpdateCheckError) as error:
                check_latest('0.1.6')
        self.assertEqual(error.exception.failures, {'api': 'timeout', 'fallback': 'timeout'})
        with patch('backend.updates.subprocess.run', side_effect=[
                response(b' ' * (LIMIT + 1) + b'\n200'), response(b'', 28)]):
            with self.assertRaises(UpdateCheckError):
                check_latest('0.1.6')
