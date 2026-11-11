"""Decky entry point. One serialized backend owns all mutations."""
import asyncio
import collections
import json
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
        self.game_known = False
        self.applied = None
        self.apply_error = None
        self.last_test = 0.0
        self.last_error = ''
        self.started_at = time.strftime('%H:%M:%S')
        self.rumble_test = {'state': 'idle', 'code': '', 'detail': ''}
        self.call_log = collections.deque(maxlen=40)
        self.trace_lock = threading.Lock()
        self.last_trace_error = None
        self.maintaining = False
        self.stopping = asyncio.Event()

    def setup(self):
        if self.store is None:
            directory = Path(os.environ['DECKY_PLUGIN_SETTINGS_DIR'])
            store = Store(directory / 'config.json')
            ip = InputPlumber(self.hardware, directory / 'management.json')
            self.store, self.ip = store, ip

    def trace(self, label, detail):
        """Bound disk logging; keep ordinary successful reads in memory only."""
        line = '%s %s %s' % (time.strftime('%H:%M:%S'), label, detail[:200])
        with self.trace_lock:
            self.call_log.append(line)
            if detail in ('start', 'cancelled') or (label == 'get_state' and detail == 'ok'):
                return
            if detail.startswith(('error ', 'raised ')):
                error = (label, detail)
                if self.last_trace_error == error:
                    return
                self.last_trace_error = error
            else:
                self.last_trace_error = None
            try:
                path = Path(os.environ['DECKY_PLUGIN_SETTINGS_DIR']) / 'calls.log'
                data = (line + '\n').encode('utf-8')
                if path.exists() and path.stat().st_size + len(data) > 64 * 1024:
                    backup = path.with_suffix('.log.1')
                    path.replace(backup)
                    if backup.stat().st_size > 64 * 1024:
                        with backup.open('rb') as stream:
                            stream.seek(-64 * 1024, 2)
                            tail = stream.read()
                        backup.write_bytes(tail)
                with path.open('ab') as stream:
                    stream.write(data)
            except Exception:
                pass

    async def operation(self, fn, label='op'):
        def run():
            with self.lock:
                return self.work(fn)
        self.trace(label, 'start')
        try:
            result = await asyncio.to_thread(run)
        except asyncio.CancelledError:
            self.trace(label, 'cancelled')
            raise
        except BaseException as exc:
            # An exception here would reach Decky, which reports only a bare
            # "Python Exception" and hides the cause from the panel.
            self.last_error = describe(exc)
            self.trace(label, 'raised ' + describe(exc))
            log.exception('Controller callable failed outside the worker')
            return {'ok': False, 'error': 'internal ' + describe(exc)}
        self.trace(label, 'ok' if result.get('ok') else 'error ' + str(result.get('error')))
        return result

    def work(self, fn):
        try:
            self.setup()
            if self.maintaining:
                raise SuiteError('maintenance_pending')
            return {'ok': True, 'data': fn()}
        except Exception as exc:
            code = str(exc) if isinstance(exc, SuiteError) else 'operation_failed'
            detail = describe(exc)
            if self.last_error != detail:
                log.exception('Controller operation failed (%s)', code)
            self.last_error = detail
            return {'ok': False, 'error': code}

    def status(self):
        state = {'config': self.store.snapshot(), 'game': self.game, 'game_name': self.game_name, 'game_known': self.game_known,
                 'applied': self.applied, 'apply_error': self.apply_error,
                 'managed': self.ip.enabled, 'last_error': self.last_error,
                 'pid': os.getpid(), 'started': self.started_at,
                 'rumble_test': dict(self.rumble_test), 'call_log': list(self.call_log)[-8:]}
        identity = None
        def hardware_state():
            nonlocal identity
            identity = self.hardware.discover()
            return self.hardware.state(identity)
        for key, call in [('hardware', hardware_state), ('inputplumber', lambda: self.ip.status(identity))]:
            try:
                state[key] = call()
            except Exception as exc:
                state[key + '_error'] = str(exc) if isinstance(exc, SuiteError) else 'interface_unavailable'
        # Read-only drift check for the panel: report it, never fix it silently.
        try:
            expected = self.ip.expected_targets
            actual = (state.get('inputplumber') or {}).get('targets')
            state['consistent'] = (not self.ip.enabled and not self.ip.restore_pending) or (
                self.ip.enabled and self.ip.ready and expected is not None and actual == expected)
        except Exception:
            state['consistent'] = False
        try:
            state['can_test'] = len(rumble.candidates(self.hardware, identity) if identity else []) == 1
        except Exception:
            state['can_test'] = False
        return state

    async def get_state(self):
        return await self.operation(self.status, 'get_state')

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
                self.game_known = False
                return {'applied': self.applied, 'apply_error': self.apply_error}
            changed = game_id != self.game
            self.game, self.game_name, self.game_known = game_id, name, True
            if changed:
                self.apply_selected()
            return {'applied': self.applied, 'apply_error': self.apply_error}
        return await self.operation(update, 'report_game')

    async def save_config(self, scope, name, rules, enabled, revision):
        def save():
            self.store.save(scope, name, rules, enabled, revision)
            self.apply_selected()
            return self.status()
        return await self.operation(save, 'save_config')

    async def delete_config(self, scope, revision):
        def delete():
            self.store.delete(scope, revision)
            self.apply_selected()
            return self.status()
        return await self.operation(delete, 'delete_config')

    async def set_hardware(self, mode, left, right):
        return await self.operation(lambda: self.hardware.set(mode, left, right), 'set_hardware')

    async def test_rumble(self):
        # The pulse lasts ~0.5 s and must not hold the callable or the device
        # queue, so it runs on its own thread and reports through status().
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
            requested = time.monotonic()
            if self.rumble_test['state'] == 'running' or requested - self.last_test < 1:
                raise SuiteError('test_busy')
            self.last_test = requested
            self.rumble_test = {'state': 'running', 'code': '', 'detail': ''}
            try:
                threading.Thread(target=pulse, name='a8-rumble-test', daemon=True).start()
            except Exception:
                self.rumble_test = {'state': 'idle', 'code': '', 'detail': ''}
                raise
            return True
        return await self.operation(start, 'test_rumble')

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
        return await self.operation(change, 'set_management')

    async def _main(self):
        # One-shot activation at plugin load. InputPlumber can start after Decky,
        # so retry for a bounded time (about 40 s) and then stop: later recovery
        # comes from explicit events (game switch, saved settings, panel retry).
        # The old 5 s device poll was removed: the target set survives suspend on
        # the tested device, and every cycle cost several D-Bus calls a second.
        for _ in range(20):
            if self.stopping.is_set():
                return
            if not self.maintaining:
                result = await self.operation(self.apply_selected, 'startup')
                if result['ok'] and not self.apply_error:
                    return
            try:
                await asyncio.wait_for(self.stopping.wait(), timeout=2)
            except asyncio.TimeoutError:
                pass

    async def check_update(self):
        # Network access is explicit and independent of the controller write lock.
        from backend.updates import UpdateCheckError, check_latest
        try:
            current = json.loads((Path(__file__).resolve().parent / 'package.json').read_text())['version']
            return {'ok': True, 'data': await asyncio.to_thread(check_latest, current)}
        except UpdateCheckError as exc:
            log.warning('Release check failed: %s', exc)
            return {'ok': False, 'error': 'update_unavailable', 'failure': exc.failures}
        except Exception:
            log.exception('Release check failed internally')
            return {'ok': False, 'error': 'update_unavailable',
                    'failure': {'api': 'internal_error', 'fallback': 'not_attempted'}}

    async def maintenance(self, action, version=None):
        def schedule():
            if action not in ('install', 'reinstall', 'uninstall', 'update'):
                raise SuiteError('invalid_rules')
            import shutil
            import subprocess
            import tempfile
            import importlib.util
            root = Path(__file__).resolve().parent
            spec = importlib.util.spec_from_file_location('suite_installer', root / 'installer.py')
            installer = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(installer)
            if action == 'update':
                import re
                from backend.updates import version_key
                if (not isinstance(version, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version)
                        or version_key(version) <= version_key(installer.VERSION)):
                    raise SuiteError('invalid_rules')
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
                                'install' if action == 'update' else action, '--decky-home', str(home),
                                *(['--update-version', version] if action == 'update' else
                                  ['--reset-controller'] if action != 'uninstall' else [])], check=True, capture_output=True, text=True, timeout=15)
            except Exception:
                shutil.rmtree(directory)
                raise
            self.maintaining = True
            return True
        return await self.operation(schedule, 'maintenance')

    async def _unload(self):
        # Updates/reloads must not reset hardware or change the saved management choice.
        self.stopping.set()
        # Wait briefly for an in-flight device write, but never block shutdown:
        # Decky kills a plugin that is still alive five seconds after the request.
        def drain():
            # Cancellation cannot stop a worker thread. Acquire and release in
            # that same worker so a cancelled await never strands the lock.
            if self.lock.acquire(timeout=2):
                self.lock.release()
        try:
            await asyncio.to_thread(drain)
        except asyncio.CancelledError:
            pass
