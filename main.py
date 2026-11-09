"""Decky entry point. One serialized backend owns all mutations."""
import asyncio
import logging
import os
from pathlib import Path
import sys
import threading
import time

# Decky loads main.py directly, not as a Python package.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / 'py_modules'))
from backend.config import Store, SuiteError, valid_id
from backend.hardware import Hardware
from backend.inputplumber import InputPlumber
from backend import rumble

log = logging.getLogger('msi-claw-a8-controller-suite')


def describe(exc):
    """Short, panel-readable description of an exception for diagnostics."""
    text = str(exc).strip()
    return (type(exc).__name__ + ': ' + text)[:300] if text else type(exc).__name__


class Plugin:
    def __init__(self):
        # A thread lock, not asyncio.Lock: the guard must never depend on which
        # event loop Decky dispatches a callable on, and a cancelled coroutine
        # must not release it while its worker thread still touches a device.
        self.lock = threading.Lock()
        self.store = None
        self.hardware = Hardware()
        self.ip = None
        self.game = None
        self.game_name = ''
        self.applied = None
        self.apply_error = None
        self.last_test = 0.0
        self.last_error = ''
        self.rumble_test = {'state': 'idle', 'code': '', 'detail': ''}
        self.maintaining = False
        self.stopping = asyncio.Event()

    def setup(self):
        if self.store is None:
            directory = Path(os.environ['DECKY_PLUGIN_SETTINGS_DIR'])
            store = Store(directory / 'config.json')
            ip = InputPlumber(self.hardware, directory / 'recovery.json')
            self.store, self.ip = store, ip

    async def operation(self, fn):
        def run():
            with self.lock:
                return self.work(fn)
        try:
            return await asyncio.to_thread(run)
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            # An exception here would reach Decky, which reports only a bare
            # "Python Exception" and hides the cause from the panel.
            self.last_error = describe(exc)
            log.exception('Controller callable failed outside the worker')
            return {'ok': False, 'error': 'internal ' + describe(exc)}

    def work(self, fn):
        try:
            self.setup()
            if self.maintaining:
                raise SuiteError('maintenance_pending')
            return {'ok': True, 'data': fn()}
        except Exception as exc:
            code = str(exc) if isinstance(exc, SuiteError) else 'operation_failed'
            self.last_error = describe(exc)
            log.exception('Controller operation failed (%s)', code)
            return {'ok': False, 'error': code}

    def status(self):
        state = {'config': self.store.snapshot(), 'game': self.game, 'game_name': self.game_name,
                 'applied': self.applied, 'apply_error': self.apply_error,
                 'managed': self.ip.enabled, 'last_error': self.last_error,
                 'rumble_test': dict(self.rumble_test)}
        for key, call in [('hardware', self.hardware.state), ('inputplumber', self.ip.status)]:
            try:
                state[key] = call()
            except Exception as exc:
                state[key + '_error'] = str(exc) if isinstance(exc, SuiteError) else 'interface_unavailable'
        try:
            state['can_test'] = len(rumble.candidates(self.hardware, self.hardware.discover())) == 1
        except Exception:
            state['can_test'] = False
        return state

    async def get_state(self):
        return await self.operation(self.status)

    def apply_selected(self):
        # Before Steam reports a game, establish the default configuration. Later
        # unknown reports retain the last known game rather than switching away.
        scope, rules = self.store.selected(self.game or 'default')
        try:
            self.ip.reconcile(rules)
            self.applied = scope if self.ip.enabled else None
            self.apply_error = None
        except Exception as exc:
            self.applied = None
            self.apply_error = str(exc) if isinstance(exc, SuiteError) else 'operation_failed'

    async def report_game(self, game_id, name):
        # Frontend reports a stable Steam app ID; None means unknown, not desktop.
        if game_id not in (None, 'default'):
            try:
                valid_id(game_id)
            except SuiteError:
                return {'ok': False, 'error': 'invalid_game'}
        if not isinstance(name, str) or len(name) > 160:
            return {'ok': False, 'error': 'invalid_game'}
        def update():
            if game_id is None:
                return {'applied': self.applied, 'apply_error': self.apply_error}
            self.game, self.game_name = game_id, name
            self.apply_selected()
            return {'applied': self.applied, 'apply_error': self.apply_error}
        return await self.operation(update)

    async def save_config(self, scope, name, rules, enabled, revision):
        def save():
            self.store.save(scope, name, rules, enabled, revision)
            self.apply_selected()
            return self.status()
        return await self.operation(save)

    async def delete_config(self, scope, revision):
        def delete():
            self.store.delete(scope, revision)
            self.apply_selected()
            return self.status()
        return await self.operation(delete)

    async def set_hardware(self, mode, left, right):
        return await self.operation(lambda: self.hardware.set(mode, left, right))

    async def test_rumble(self):
        # The pulse lasts ~0.5 s and must not hold the callable or the device
        # queue, so it runs on its own thread and reports through status().
        requested = time.monotonic()
        if requested - self.last_test < 1:
            return {'ok': False, 'error': 'test_busy'}
        self.last_test = requested
        self.rumble_test = {'state': 'running', 'code': '', 'detail': ''}

        def pulse():
            try:
                rumble.pulse(self.hardware)
                self.rumble_test = {'state': 'ok', 'code': '', 'detail': ''}
            except Exception as exc:
                code = str(exc) if isinstance(exc, SuiteError) else 'operation_failed'
                self.rumble_test = {'state': 'error', 'code': code, 'detail': describe(exc)}
                self.last_error = describe(exc)
                log.exception('Rumble test failed (%s)', code)

        def start():
            threading.Thread(target=pulse, name='a8-rumble-test', daemon=True).start()
            return True
        return await self.operation(start)

    async def set_management(self, enabled):
        def change():
            if type(enabled) is not bool:
                raise SuiteError('invalid_rules')
            # Persist intent before touching hardware. A failed restore must never
            # cause a reboot to silently re-enable management.
            self.ip.set_enabled(enabled)
            self.ip.ready = False
            self.apply_selected()
            return self.status()
        return await self.operation(change)

    async def _main(self):
        # Independent of the panel/frontend: late devices, reboot and wake recover.
        while not self.stopping.is_set():
            await self.operation(self.apply_selected)
            try:
                await asyncio.wait_for(self.stopping.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass

    async def maintenance(self, action):
        def schedule():
            if action not in ('install', 'reinstall', 'uninstall'):
                raise SuiteError('invalid_rules')
            import shutil
            import subprocess
            import tempfile
            import importlib.util
            root = Path(__file__).resolve().parent
            spec = importlib.util.spec_from_file_location('suite_installer', root / 'installer.py')
            installer = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(installer)
            home = installer.validate_home(os.environ['DECKY_HOME'])
            if root != home / 'plugins' / installer.FOLDER:
                raise SuiteError('nonstandard_install')
            if Path(os.environ['DECKY_PLUGIN_SETTINGS_DIR']).resolve() != home / 'settings' / installer.FOLDER:
                raise SuiteError('nonstandard_install')
            directory = Path(tempfile.mkdtemp(prefix='msi-claw-a8-controller-suite-maintenance-', dir='/run'))
            try:
                for name in ('installer.py', 'maintenance_runner.py'):
                    shutil.copyfile(root / name, directory / name)
                subprocess.run(['systemd-run', '--unit=msi-claw-a8-controller-suite-maintenance', '--on-active=3s',
                                '--collect', '/usr/bin/python3', str(directory / 'maintenance_runner.py'),
                                action, '--decky-home', str(home)], check=True, capture_output=True, text=True, timeout=15)
            except Exception:
                shutil.rmtree(directory)
                raise
            self.maintaining = True
            return True
        return await self.operation(schedule)

    async def _unload(self):
        # Updates/reloads must not reset hardware or destroy the recovery snapshot.
        self.stopping.set()
        # Wait for an in-flight device write instead of interleaving with it.
        await asyncio.to_thread(self.lock.acquire)
        self.lock.release()
