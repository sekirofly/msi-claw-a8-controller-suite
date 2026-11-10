import ctypes
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.hardware import Hardware, ATTRS
from backend.config import SuiteError
from backend.rumble import Effect, has_rumble


class HardwareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sys = Path(self.tmp.name)
        dmi = self.sys / 'class/dmi/id'
        dmi.mkdir(parents=True)
        (dmi/'board_name').write_text('MS-1T8K')
        (dmi/'board_vendor').write_text('Micro-Star International Co., Ltd.')
        self.hw = Hardware(self.sys)

    def test_reset_does_not_save_or_reapply_hardware_settings(self):
        device = self.sys / 'controller'
        device.mkdir()
        (device / 'reset').write_text('')
        (device / 'mkeys_function').write_text('macro')
        (device / 'rumble_intensity_left').write_text('35')
        with patch.object(self.hw, 'discover', return_value={'path': device}), patch('os.geteuid', return_value=0):
            self.hw.reset_controller()
        self.assertEqual((device / 'reset').read_text(), '1\n')
        self.assertEqual((device / 'mkeys_function').read_text(), 'macro')
        self.assertEqual((device / 'rumble_intensity_left').read_text(), '35')
        (device / 'reset').unlink()
        with patch.object(self.hw, 'discover', return_value={'path': device}), patch('os.geteuid', return_value=0):
            with self.assertRaisesRegex(SuiteError, 'reset_unavailable'):
                self.hw.reset_controller()

    def usb(self, port='3'):
        p = self.sys / 'devices/pci0000:00/0000:c6:00.0/usb1' / ('1-'+port)
        p.mkdir(parents=True, exist_ok=True)
        for name, value in [('idVendor','0db0'),('idProduct','1901'),('devpath',port)]: (p/name).write_text(value)
        return p

    @unittest.skipUnless(__import__('os').name == 'posix', 'Linux PCI path fixture')
    def test_external_same_model_rejected(self):
        self.assertIsNone(self.hw.usb(self.usb('4')))
        self.assertIsNotNone(self.hw.usb(self.usb('3')))

    def test_non_a8_host_rejected(self):
        (self.sys/'class/dmi/id/board_name').write_text('Other')
        with self.assertRaisesRegex(SuiteError,'not_a8'): self.hw.discover()

    @unittest.skipUnless(__import__('os').name == 'posix', 'Linux sysfs symlink fixture')
    def test_realpath_discovery_and_write(self):
        p = self.usb()/'hid'
        p.mkdir()
        for attr,value in zip(ATTRS, ('macro','80','90')): (p/attr).write_text(value)
        link=self.sys/'class/hidraw/hidraw7/device'
        link.parent.mkdir(parents=True)
        link.symlink_to(p, target_is_directory=True)
        self.assertEqual(self.hw.state()['left'],80)
        with patch('os.geteuid', return_value=0): self.hw.set(left=0, right=100)
        self.assertEqual(self.hw.state()['right'],100)
        with self.assertRaises(SuiteError): self.hw.set(left=True)

    def test_ff_bitmap_uses_word_boundaries(self):
        p=self.sys/'event0/device/capabilities';p.mkdir(parents=True)
        (p/'ff').write_text('10000 0')
        self.assertTrue(has_rumble(self.sys/'event0'))
        (p/'ff').write_text('0')
        self.assertFalse(has_rumble(self.sys/'event0'))

    def test_effect_abi_and_duration(self):
        self.assertEqual(ctypes.sizeof(Effect),48)
        effect=Effect(type=0x50,id=-1,length=500)
        self.assertEqual(effect.length,500)
