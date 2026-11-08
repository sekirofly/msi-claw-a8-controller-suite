"""Read-only protocol smoke test against CI's real systemd, never a controller."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from backend.inputplumber import Bus


class BusTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'posix' and Path('/run/dbus/system_bus_socket').exists(), 'Requires Linux system bus')
    def test_real_busctl_property_and_call_encoding(self):
        with patch('backend.inputplumber.SERVICE', 'org.freedesktop.systemd1'):
            bus = Bus()
            version = bus.property('/org/freedesktop/systemd1', 'org.freedesktop.systemd1.Manager', 'Version')
            self.assertIsInstance(version, str)
            self.assertGreater(len(version), 2)
            path = bus.call('/org/freedesktop/systemd1', 'org.freedesktop.systemd1.Manager', 'GetUnit', 's', 'dbus.service')
            self.assertIsInstance(path, str)
            self.assertTrue(path.startswith('/org/freedesktop/systemd1/unit/'))
