import io
import json
from pathlib import Path
import tempfile
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

    def test_unconfirmed_recovery_only_warns_when_installing(self):
        # An install must not be blocked by a restore that cannot be confirmed:
        # that leaves the user unable to update or repair anything.
        snapshot = self.active_snapshot()
        with patch.object(installer.subprocess, 'run', side_effect=RuntimeError('offline')):
            installer.restore_before_removal(self.home, fatal=False)
        self.assertTrue(json.loads(snapshot.read_text())['active'])
        self.assertEqual((self.target / 'old.txt').read_text(), 'old')

    def test_recovery_precedes_delete_and_keeps_emergency_copy(self):
        snapshot = self.active_snapshot()
        def restore(*args, **kwargs):
            self.assertTrue((self.target / 'old.txt').exists())
            snapshot.write_text('{"active":false}')
        with patch.object(installer, 'service'), patch.object(installer.subprocess, 'run', side_effect=restore):
            installer.transact(self.home, 'uninstall')
        self.assertFalse(snapshot.exists())
        self.assertFalse(self.target.exists())
        self.assertEqual(len(list((self.home / ('.'+installer.FOLDER+'-recovery')).glob('*.json'))), 1)

    def test_install_update_preserves_configuration(self):
        snapshot = self.active_snapshot()
        def restore(*args, **kwargs): snapshot.write_text('{"active":false}')
        staged = self.home / 'stage'
        staged.mkdir()
        (staged / 'plugin.json').write_text(json.dumps({'name': installer.NAME}))
        with patch.object(installer, 'service'), patch.object(installer.subprocess, 'run', side_effect=restore), patch.object(installer.os, 'chown', create=True):
            installer.transact(self.home, 'install', staged)
        self.assertEqual((snapshot.parent / 'config.json').read_text(), '{"keep":"config"}')
        self.assertFalse(json.loads(snapshot.read_text())['active'])
        self.assertTrue(json.loads((snapshot.parent / 'management.json').read_text())['enabled'])

    def test_failed_update_restoration_preserves_disabled_preference(self):
        snapshot = self.active_snapshot()
        preference = snapshot.parent / 'management.json'
        preference.write_text('{"enabled":false}')
        def fail(*args, **kwargs):
            preference.write_text('{"enabled":false}')
            raise RuntimeError('device offline')
        with patch.object(installer, 'service'), patch.object(installer.subprocess, 'run', side_effect=fail):
            with self.assertRaises(RuntimeError):
                installer.transact(self.home, 'install')
        self.assertFalse(json.loads(preference.read_text())['enabled'])
        self.assertTrue(json.loads(snapshot.read_text())['active'])

    def test_corrupt_snapshot_blocks_removal(self):
        snapshot = self.active_snapshot()
        snapshot.write_text('corrupt')
        with patch.object(installer, 'service'):
            with self.assertRaises(ValueError): installer.transact(self.home, 'uninstall')
        self.assertTrue(self.target.exists())
        self.assertEqual(snapshot.read_text(), 'corrupt')


if __name__ == '__main__':
    unittest.main()
