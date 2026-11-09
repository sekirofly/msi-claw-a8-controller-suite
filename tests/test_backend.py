import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import threading
from unittest.mock import patch
from backend.config import Store
from main import Plugin


class BackendTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.plugin=Plugin();self.plugin.store=Store(Path(self.tmp.name)/'config.json')
        self.applied=[]
        self.plugin.ip=SimpleNamespace(enabled=True, reconcile=lambda rules:self.applied.append(rules))
        self.plugin.status=lambda:{'config':self.plugin.store.snapshot(),'apply_error':self.plugin.apply_error}

    async def test_saving_inactive_game_does_not_apply_its_rules(self):
        self.plugin.game='1'
        result=await self.plugin.save_config('2','Other',{'M1':['A']},True,0)
        self.assertTrue(result['ok'])
        self.assertEqual(self.applied,[{}])
        self.assertEqual(self.plugin.applied,'default')

    async def test_save_survives_apply_failure(self):
        self.plugin.game='1'
        def fail(rules):raise RuntimeError('offline')
        self.plugin.ip.reconcile=fail
        result=await self.plugin.save_config('1','Game',{'M1':['A']},True,0)
        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['apply_error'],'operation_failed')
        self.assertEqual(self.plugin.store.selected('1')[1],{'M1':['A']})

    async def test_unknown_game_does_not_apply_default(self):
        result=await self.plugin.report_game(None,'')
        self.assertTrue(result['ok'])
        self.assertEqual(self.applied,[])

    async def test_operations_serialized(self):
        order=[]
        import time
        def first():order.append('start');time.sleep(.03);order.append('end')
        await asyncio.gather(self.plugin.operation(first),self.plugin.operation(lambda:order.append('second')))
        self.assertEqual(order,['start','end','second'])

    async def test_backend_starts_without_frontend_and_unloads(self):
        task = asyncio.create_task(self.plugin._main())
        for _ in range(50):
            if self.applied:
                break
            await asyncio.sleep(.01)
        await self.plugin._unload()
        await asyncio.wait_for(task, 1)
        self.assertEqual(self.applied, [{}])

    async def test_unknown_report_retains_known_game(self):
        await self.plugin.report_game('12', 'Game')
        await self.plugin.report_game(None, '')
        self.assertEqual(self.plugin.game, '12')
        self.assertEqual(self.plugin.game_name, 'Game')

    async def test_cancelled_unload_does_not_strand_lock(self):
        entered = threading.Event()
        real_lock = self.plugin.lock
        class ObservedLock:
            def acquire(self, **kwargs):
                entered.set()
                return real_lock.acquire(**kwargs)
            def release(self):
                real_lock.release()
        self.plugin.lock = ObservedLock()
        real_lock.acquire()
        task = asyncio.create_task(self.plugin._unload())
        try:
            self.assertTrue(await asyncio.to_thread(entered.wait, 1))
            task.cancel()
            await task
        finally:
            real_lock.release()
        # Let the cancelled worker finish, then ensure future work can acquire.
        await asyncio.sleep(.05)
        acquired = real_lock.acquire(timeout=.2)
        self.assertTrue(acquired)
        if acquired:
            real_lock.release()

    async def test_long_rumble_cannot_overlap_and_maintenance_does_not_mark_running(self):
        release = threading.Event()
        finished = threading.Event()
        def pulse(hardware):
            try:
                release.wait(2)
            finally:
                finished.set()
        with patch('main.rumble.pulse', side_effect=pulse) as mocked:
            try:
                self.assertTrue((await self.plugin.test_rumble())['ok'])
                self.plugin.last_test = 0  # cooldown expired, pulse still running
                self.assertEqual((await self.plugin.test_rumble())['error'], 'test_busy')
                self.assertEqual(mocked.call_count, 1)
            finally:
                release.set()
                await asyncio.to_thread(finished.wait, 1)
        self.plugin.maintaining = True
        self.plugin.rumble_test = {'state': 'idle', 'code': '', 'detail': ''}
        self.assertEqual((await self.plugin.test_rumble())['error'], 'maintenance_pending')
        self.assertEqual(self.plugin.rumble_test['state'], 'idle')

    async def test_startup_retries_setup_failure(self):
        calls = []
        async def operation(*args):
            calls.append(True)
            if len(calls) == 1:
                return {'ok': False, 'error': 'operation_failed'}
            return {'ok': True, 'data': None}
        async def immediate_timeout(awaitable, timeout):
            awaitable.close()
            raise asyncio.TimeoutError
        with patch.object(self.plugin, 'operation', side_effect=operation), \
             patch('main.asyncio.wait_for', side_effect=immediate_timeout):
            await self.plugin._main()
        self.assertEqual(len(calls), 2)
