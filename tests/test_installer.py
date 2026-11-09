import io
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch
import zipfile
import installer


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve() / 'homebrew'
        self.target = self.home / 'plugins' / 'msi-claw-a8-controller-suite'
        self.target.mkdir(parents=True)
        (self.target / 'plugin.json').write_text(json.dumps({'name': installer.NAME}))
        (self.target / 'old.txt').write_text('old')
        (self.target / 'recover.py').write_text('# fixture')
        runner = patch.object(installer.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', ''))
        runner.start(); self.addCleanup(runner.stop)
        self.other = self.home / 'plugins' / 'OtherPlugin'
        self.other.mkdir()
        (self.other / 'keep.txt').write_text('keep')

    def test_uninstall_only_own_files(self):
        own = self.home / 'settings' / 'msi-claw-a8-controller-suite'
        own.mkdir(parents=True)
        (own / 'settings.json').write_text('{}')
        with patch.object(installer, 'service'):
            installer.transact(self.home, 'uninstall')
        self.assertFalse(self.target.exists())
        self.assertFalse(own.exists())
        self.assertEqual((self.other / 'keep.txt').read_text(), 'keep')

    def test_start_failure_restores_installation(self):
        calls = []
        def service(action):
            calls.append(action)
            if calls.count('start') == 1 and action == 'start':
                raise RuntimeError('service failed')
        with patch.object(installer, 'service', side_effect=service):
            with self.assertRaises(RuntimeError):
                installer.transact(self.home, 'uninstall')
        self.assertEqual((self.target / 'old.txt').read_text(), 'old')

    def test_partial_copy_rolls_back(self):
        staged = self.home / 'stage'
        staged.mkdir()
        def fail_copy(source, target):
            target.mkdir()
            (target / 'partial').write_text('broken')
            raise OSError('disk full')
        with patch.object(installer, 'service'), patch.object(installer.shutil, 'copytree', side_effect=fail_copy):
            with self.assertRaises(OSError):
                installer.transact(self.home, 'reinstall', staged)
        self.assertEqual((self.target / 'old.txt').read_text(), 'old')
        self.assertFalse((self.target / 'partial').exists())

    def test_wrong_identity_is_not_deleted(self):
        (self.target / 'plugin.json').write_text('{"name":"Other"}')
        with self.assertRaises(ValueError):
            installer.transact(self.home, 'uninstall')
        self.assertTrue((self.target / 'old.txt').exists())

    def test_stop_failure_keeps_files(self):
        with patch.object(installer, 'service', side_effect=RuntimeError('cannot stop')):
            with self.assertRaises(RuntimeError):
                installer.transact(self.home, 'uninstall')
        self.assertEqual((self.target / 'old.txt').read_text(), 'old')

    def test_successful_reinstall(self):
        staged = self.home / 'stage'
        staged.mkdir()
        (staged / 'plugin.json').write_text(json.dumps({'name': installer.NAME}))
        (staged / 'new.txt').write_text('new')
        with patch.object(installer, 'service'), patch.object(installer.os, 'chown', create=True):
            installer.transact(self.home, 'reinstall', staged)
        self.assertFalse((self.target / 'old.txt').exists())
        self.assertEqual((self.target / 'new.txt').read_text(), 'new')
        self.assertEqual((self.other / 'keep.txt').read_text(), 'keep')

    def test_rollback_failure_preserves_backup(self):
        def service(action):
            if action == 'start':
                raise RuntimeError('cannot start')
        with patch.object(installer, 'service', side_effect=service):
            with self.assertRaises(RuntimeError):
                installer.transact(self.home, 'uninstall')
        self.assertEqual((self.target / 'old.txt').read_text(), 'old')

    @unittest.skipIf(__import__('os').name == 'nt', 'Linux symlink test')
    def test_symlink_is_rejected(self):
        link = self.home / 'settings'
        link.symlink_to(self.other, target_is_directory=True)
        with self.assertRaises(ValueError):
            installer.transact(self.home, 'uninstall')
        self.assertTrue((self.other / 'keep.txt').exists())

    def test_archive_traversal(self):
        for filename in ('../escape', 'msi-claw-a8-controller-suite/../../escape', '/etc/passwd', 'Other/main.py', 'msi-claw-a8-controller-suite\\escape'):
            data = io.BytesIO()
            with zipfile.ZipFile(data, 'w') as archive:
                archive.writestr(filename, 'bad')
            with self.assertRaises(ValueError):
                installer.unpack(data.getvalue(), self.home / 'extracted')

    def test_archive_symlink(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            info = zipfile.ZipInfo('msi-claw-a8-controller-suite/link')
            info.external_attr = 0o120777 << 16
            archive.writestr(info, '/etc')
        with self.assertRaises(ValueError):
            installer.unpack(data.getvalue(), self.home / 'extracted')

    def active_snapshot(self):
        directory = self.home / 'settings' / installer.FOLDER
        directory.mkdir(parents=True)
        snapshot = directory / 'recovery.json'
        snapshot.write_text(json.dumps({'active': True, 'original_profile': {'name': 'original'}}))
        (directory / 'config.json').write_text('{"keep":"config"}')
        (self.target / 'recover.py').write_text('# recovery fixture')
        return snapshot

    def test_recovery_failure_preserves_files_and_snapshot(self):
        snapshot = self.active_snapshot()
        with patch.object(installer, 'service'), patch.object(installer.subprocess, 'run', side_effect=RuntimeError('offline')):
            with self.assertRaises(RuntimeError): installer.transact(self.home, 'uninstall')
        self.assertTrue(snapshot.exists())
        self.assertTrue(json.loads(snapshot.read_text())['active'])
        self.assertEqual((self.target / 'old.txt').read_text(), 'old')
        self.assertEqual(len(list((self.home / ('.'+installer.FOLDER+'-recovery')).glob('*.json'))), 1)

    def test_uninstall_failed_default_restore_preserves_installation_without_snapshot(self):
        with patch.object(installer, 'service'), patch.object(installer.subprocess, 'run',
                return_value=subprocess.CompletedProcess([], 1, '', 'defaults missing')):
            with self.assertRaisesRegex(ValueError, 'defaults missing'):
                installer.transact(self.home, 'uninstall')
        self.assertTrue((self.target / 'old.txt').exists())

    def test_uninstall_restores_even_without_legacy_snapshot(self):
        with patch.object(installer, 'service'), patch.object(installer.subprocess, 'run',
                return_value=subprocess.CompletedProcess([], 0, '', '')) as run:
            installer.transact(self.home, 'uninstall')
        run.assert_called_once()
        self.assertFalse(self.target.exists())

    def test_recovery_precedes_delete_and_keeps_emergency_copy(self):
        snapshot = self.active_snapshot()
        def restore(*args, **kwargs):
            self.assertTrue((self.target / 'old.txt').exists())
            return subprocess.CompletedProcess([], 0, 'System defaults restored', '')
        with patch.object(installer, 'service'), patch.object(installer.subprocess, 'run', side_effect=restore):
            installer.transact(self.home, 'uninstall')
        self.assertFalse(snapshot.exists())
        self.assertFalse(self.target.exists())
        self.assertEqual(len(list((self.home / ('.'+installer.FOLDER+'-recovery')).glob('*.json'))), 1)

    def test_install_update_preserves_configuration(self):
        # An update keeps the configuration, the snapshot and the management
        # choice untouched: the new version re-applies from that snapshot
        # instead of restoring first, so nothing in settings is rewritten.
        snapshot = self.active_snapshot()
        preference = snapshot.parent / 'management.json'
        preference.write_text('{"enabled":false}')
        staged = self.home / 'stage'
        staged.mkdir()
        (staged / 'plugin.json').write_text(json.dumps({'name': installer.NAME}))
        with patch.object(installer, 'service'), patch.object(installer.os, 'chown', create=True):
            installer.transact(self.home, 'install', staged)
        self.assertEqual((snapshot.parent / 'config.json').read_text(), '{"keep":"config"}')
        self.assertTrue(json.loads(snapshot.read_text())['active'])
        self.assertFalse(json.loads(preference.read_text())['enabled'])

    def test_update_does_not_touch_the_controller(self):
        # A plain update replaces files only. Restoring first rebuilt every
        # InputPlumber target object, which made updates slow and could fail for
        # no benefit: the new version re-applies on start.
        snapshot = self.active_snapshot()
        preference = snapshot.parent / 'management.json'
        preference.write_text('{"enabled":false}')
        staged = self.home / 'stage'
        staged.mkdir()
        (staged / 'plugin.json').write_text(json.dumps({'name': installer.NAME}))
        calls = []
        def record(*args, **kwargs):
            calls.append(args)
            return None
        with patch.object(installer, 'service'), patch.object(installer.subprocess, 'run', side_effect=record), \
             patch.object(installer.os, 'chown', create=True):
            installer.transact(self.home, 'install', staged)
        self.assertEqual(calls, [], 'an update must not run recover.py or any subprocess')
        self.assertFalse(json.loads(preference.read_text())['enabled'])
        self.assertTrue(json.loads(snapshot.read_text())['active'])
        self.assertTrue((self.target / 'plugin.json').exists())

    def test_corrupt_legacy_snapshot_does_not_block_uninstall(self):
        snapshot = self.active_snapshot()
        snapshot.write_text('corrupt legacy backup')
        with patch.object(installer, 'service'):
            installer.transact(self.home, 'uninstall')
        copies = list((self.home / ('.' + installer.FOLDER + '-recovery')).glob('*.json'))
        self.assertEqual(copies[0].read_text(), 'corrupt legacy backup')
        self.assertFalse(self.target.exists())

    def test_skip_restore_uninstall_keeps_emergency_snapshot(self):
        snapshot = self.active_snapshot()
        original = snapshot.read_bytes()
        with patch.object(installer, 'service'):
            installer.transact(self.home, 'uninstall', skip_restore=True)
        copies = list((self.home / ('.' + installer.FOLDER + '-recovery')).glob('*.json'))
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].read_bytes(), original)

    def test_reinstall_archives_legacy_backup_and_retains_preference(self):
        for skip in (False, True):
            with self.subTest(skip=skip):
                settings = self.home / 'settings' / installer.FOLDER
                settings.mkdir(parents=True, exist_ok=True)
                original = {'active': True, 'original_profile': {'name': 'original'}}
                (settings / 'recovery.json').write_text(json.dumps(original))
                (settings / 'management.json').write_text('{"enabled":false}')
                (settings / 'config.json').write_text('{}')
                (self.target / 'recover.py').write_text('# fixture')
                staged = self.home / ('stage-' + str(skip))
                staged.mkdir()
                (staged / 'plugin.json').write_text(json.dumps({'name': installer.NAME}))
                with patch.object(installer, 'service'), patch.object(installer.os, 'chown'), \
                     patch.object(installer.subprocess, 'run') as run:
                    installer.transact(self.home, 'reinstall', staged, skip_restore=skip)
                run.assert_not_called()
                self.assertFalse((settings / 'recovery.json').exists())
                copies = list((self.home / ('.' + installer.FOLDER + '-recovery')).glob('*.json'))
                self.assertTrue(any(json.loads(p.read_text()) == original for p in copies))
                self.assertFalse(json.loads((settings / 'management.json').read_text())['enabled'])
                self.assertFalse((settings / 'config.json').exists())


if __name__ == '__main__':
    unittest.main()
