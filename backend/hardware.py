"""A8-specific discovery and sysfs controls; derived from the MIT v1.0.1 plugin.

Copyright (c) 2026 sekirofly. Original notice: third_party/hardware-controls-MIT.txt.
The internal USB port is pinned to the upstream MS-1T8K definition; unknown
topologies fail closed rather than guessing another connected controller.
"""
import os
import re
from pathlib import Path
from .config import SuiteError

ATTRS = ('mkeys_function', 'rumble_intensity_left', 'rumble_intensity_right')
MODES = ('macro', 'combination', 'disabled')


def read(path):
    return Path(path).read_text(encoding='ascii').strip()


class Hardware:
    def __init__(self, sys=Path('/sys')):
        self.sys = Path(sys)

    def board(self):
        dmi = self.sys / 'class/dmi/id'
        if read(dmi / 'board_name') != 'MS-1T8K' or read(dmi / 'board_vendor') != 'Micro-Star International Co., Ltd.':
            raise SuiteError('not_a8')

    def usb(self, path):
        for parent in [path.resolve(), *path.resolve().parents]:
            if not (parent / 'idVendor').is_file():
                continue
            if read(parent / 'idVendor') != '0db0' or read(parent / 'idProduct') not in ('1901', '1902'):
                return None
            if read(parent / 'devpath') != '3' or '0000:c6:00.0' not in [p.name for p in parent.parents]:
                return None
            return parent
        return None

    def discover(self):
        self.board()
        candidates = {}
        for path in (self.sys / 'class/hidraw').glob('hidraw*/device'):
            if all((path / a).is_file() for a in ATTRS) and self.usb(path):
                candidates[str(path.resolve())] = path.resolve()
        if len(candidates) != 1:
            raise SuiteError('device_ambiguous' if candidates else 'device_missing')
        path = next(iter(candidates.values()))
        usb = self.usb(path)
        events = [str(p) for p in (self.sys / 'class/input').glob('event*') if self.usb(p / 'device') == usb]
        return {'path': path, 'usb': str(usb), 'events': events}

    def matches_source(self, source, identity):
        name = Path(source).name
        if re.fullmatch(r'event[0-9]+', name):
            return self.usb(self.sys / 'class/input' / name / 'device') == Path(identity['usb'])
        if re.fullmatch(r'hidraw[0-9]+', name):
            return self.usb(self.sys / 'class/hidraw' / name / 'device') == Path(identity['usb'])
        return False

    def state(self):
        identity = self.discover()
        p = identity['path']
        mode, left, right = read(p / ATTRS[0]), int(read(p / ATTRS[1])), int(read(p / ATTRS[2]))
        if mode not in MODES or not (0 <= left <= 100 and 0 <= right <= 100):
            raise SuiteError('invalid_hardware_state')
        return {'mode': mode, 'left': left, 'right': right, 'identity': identity['usb']}

    def reset_controller(self):
        """Reset only the verified internal controller; do not save/reapply settings."""
        if os.geteuid() != 0:
            raise SuiteError('root_required')
        identity = self.discover()
        reset = identity['path'] / 'reset'
        if not reset.is_file() or reset.is_symlink():
            raise SuiteError('reset_unavailable')
        if self.discover()['path'] != identity['path']:
            raise SuiteError('device_changed')
        reset.write_text('1\n', encoding='ascii')

    def set(self, mode=None, left=None, right=None):
        if os.geteuid() != 0:
            raise SuiteError('root_required')
        if mode is not None and mode not in MODES:
            raise SuiteError('invalid_rules')
        for value in (left, right):
            if value is not None and (type(value) is not int or not 0 <= value <= 100):
                raise SuiteError('invalid_rules')
        identity = self.discover()
        for attr, value in zip(ATTRS, (mode, left, right)):
            if value is not None:
                if self.discover()['usb'] != identity['usb']:
                    raise SuiteError('device_changed')
                p = identity['path'] / attr
                if read(p) != str(value):
                    p.write_text(str(value) + '\n', encoding='ascii')
                if read(p) != str(value):
                    raise SuiteError('readback_failed')
        return self.state()
