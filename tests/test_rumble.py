import os
import stat
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from backend.rumble import pulse, Effect


@unittest.skipUnless(os.name == 'posix', 'Linux ioctl effect lifecycle')
class RumbleTests(unittest.TestCase):
    def test_finite_effect_cleanup_even_on_wait_failure(self):
        hardware = SimpleNamespace(discover=lambda:{'usb':'embedded','events':['/sys/class/input/event7']})
        calls=[]
        def ioctl(fd, request, data, *args):
            calls.append((fd,request,data))
            if request==0x40304580:
                effect=Effect.from_buffer(data)
                self.assertEqual(effect.length,500)
                self.assertEqual(effect.payload.rumble.strong,65535)
                effect.id=3
        with patch('backend.rumble.candidates',return_value=['/sys/class/input/event7']), \
             patch('backend.rumble.read_dev',return_value=42), \
             patch('pathlib.Path.stat',return_value=SimpleNamespace(st_mode=stat.S_IFCHR,st_rdev=42)), \
             patch('os.open',return_value=9), \
             patch('os.fstat',return_value=SimpleNamespace(st_rdev=42)), \
             patch('os.write') as write, patch('os.close') as close:
            with self.assertRaisesRegex(RuntimeError,'interrupted'):
                pulse(hardware,ioctl=ioctl,sleep=lambda _:(_ for _ in ()).throw(RuntimeError('interrupted')))
            self.assertEqual(write.call_count,2)
            self.assertEqual(calls[-1],(9,0x40044581,3))
            close.assert_called_once_with(9)

    def test_no_candidate_never_opens_device(self):
        hardware=SimpleNamespace(discover=lambda:{'usb':'embedded','events':[]})
        with patch('backend.rumble.candidates',return_value=[]),patch('os.open') as opened:
            with self.assertRaisesRegex(Exception,'rumble_unavailable'):pulse(hardware)
            opened.assert_not_called()
