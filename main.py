"""Decky entry point. One serialized backend owns all mutations."""
import asyncio
import logging
import os
from pathlib import Path
import sys
import time

# Decky loads main.py directly, not as a Python package.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend.config import Store, SuiteError, valid_id
from backend.hardware import Hardware
from backend.inputplumber import InputPlumber
from backend import rumble

log = logging.getLogger('msi-claw-a8-controller-suite')


class Plugin:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.store = None
        self.hardware = Hardware()
        self.ip = None
        self.game = None
        self.game_name = ''
        self.applied = None
        self.apply_error = None
        self.last_test = 0.0

    def setup(self):
        if self.store is None:
            directory = Path(os.environ['DECKY_PLUGIN_SETTINGS_DIR'])
            self.store = Store(directory / 'config.json')
            self.ip = InputPlumber(self.hardware, directory / 'recovery.json')

    async def operation(self, fn):
        async with self.lock:
            task = asyncio.create_task(asyncio.to_thread(self.work, fn))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                # Never release the lock while its worker is still touching a device.
                await task
                raise

    def work(self, fn):
        try:
            self.setup()
            return {'ok': True, 'data': fn()}
        except Exception as exc:
            code = str(exc) if isinstance(exc, SuiteError) else 'operation_failed'
            log.exception('Controller operation failed (%s)', code)
            return {'ok': False, 'error': code}

    def status(self):
        state = {'config': self.store.snapshot(), 'game': self.game, 'game_name': self.game_name,
                 'applied': self.applied, 'apply_error': self.apply_error,
                 'managed': bool(self.ip.snapshot and self.ip.snapshot.get('active')),
                 'paused': bool(self.ip.snapshot and self.ip.snapshot.get('paused'))}
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
        if self.game is None:
            self.apply_error = 'game_unknown'
            return
        if not self.ip.snapshot or not self.ip.snapshot.get('active'):
            self.applied = None
            self.apply_error = None
            return
        scope, rules = self.store.selected(self.game)
        try:
            self.ip.apply(rules)
            self.applied = scope
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
        self.game, self.game_name = game_id, name
        def update():
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
        requested = time.monotonic()
        if requested - self.last_test < 1:
            return {'ok': False, 'error': 'test_busy'}
        self.last_test = requested
        def test():
            if time.monotonic() - requested > 2:
                raise SuiteError('test_expired')
            rumble.pulse(self.hardware)
            return True
        return await self.operation(test)

    async def set_management(self, enabled):
        def change():
            if type(enabled) is not bool:
                raise SuiteError('invalid_rules')
            if enabled:
                self.ip.enable()
                self.apply_selected()
            else:
                self.ip.restore()
                self.applied = None
                self.apply_error = None
            return self.status()
        return await self.operation(change)

    async def _main(self):
        # Explicit activation is required. Reading the panel never activates it.
        pass

    async def _unload(self):
        # Updates/reloads must not reset hardware or destroy the recovery snapshot.
        async with self.lock:
            pass
