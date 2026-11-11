import unittest
from unittest.mock import patch

import installer
import maintenance_runner


class MaintenanceRunnerTests(unittest.TestCase):
    def test_update_pins_selected_release_and_uses_preserving_install(self):
        original = installer.VERSION
        seen = []
        with patch.object(installer, 'main', side_effect=lambda argv: seen.append((installer.VERSION, argv))):
            maintenance_runner.run(['install', '--decky-home', '/tmp/home with spaces',
                                    '--update-version', '9.8.7'])
        self.assertEqual(seen, [('9.8.7', ['install', '--decky-home', '/tmp/home with spaces'])])
        self.assertEqual(installer.VERSION, original)

    def test_update_rejects_downgrades_invalid_tags_destructive_actions_and_reset(self):
        for argv in (['install', '--update-version', '0.0.1'],
                     ['install', '--update-version', installer.VERSION],
                     ['install', '--update-version', '../main'],
                     ['install', '--update-version', '9.8.7-alpha.1'],
                     ['reinstall', '--update-version', '9.8.7'],
                     ['uninstall', '--update-version', '9.8.7'],
                     ['install', '--reset-controller', '--update-version', '9.8.7']):
            with self.subTest(argv=argv), patch.object(installer, 'main') as main:
                with self.assertRaises(ValueError):
                    maintenance_runner.run(argv)
                main.assert_not_called()

    def test_ordinary_repair_arguments_are_unchanged_and_failure_restores_pin(self):
        with patch.object(installer, 'main') as main:
            maintenance_runner.run(['install', '--reset-controller'])
            main.assert_called_once_with(['install', '--reset-controller'])
        original = installer.VERSION
        with patch.object(installer, 'main', side_effect=ValueError('checksum mismatch')):
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                maintenance_runner.run(['install', '--update-version', '9.8.7'])
        self.assertEqual(installer.VERSION, original)
