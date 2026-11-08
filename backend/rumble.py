"""Finite Linux evdev FF_RUMBLE effect, scoped to one verified physical A8 node."""
import ctypes
import os
import stat
import struct
import time
from pathlib import Path
from .config import SuiteError


class Rumble(ctypes.Structure):
    _fields_ = [('strong', ctypes.c_uint16), ('weak', ctypes.c_uint16)]


class EffectUnion(ctypes.Union):
    _fields_ = [('rumble', Rumble), ('alignment', ctypes.c_uint64 * 4)]


class Effect(ctypes.Structure):
    _fields_ = [('type', ctypes.c_uint16), ('id', ctypes.c_int16),
                ('direction', ctypes.c_uint16), ('trigger_button', ctypes.c_uint16),
                ('trigger_interval', ctypes.c_uint16), ('length', ctypes.c_uint16),
                ('delay', ctypes.c_uint16), ('payload', EffectUnion)]


def has_rumble(event):
    # Kernel sysfs bitmap is printed highest machine word first.
    bits = 0
    for word in Path(event, 'device/capabilities/ff').read_text().split():
        bits = (bits << 64) | int(word, 16)
    return bool(bits & (1 << 0x50))


def candidates(hardware, identity):
    found = []
    for event in identity['events']:
        try:
            if has_rumble(event):
                found.append(event)
        except (OSError, ValueError):
            continue
    return found


def pulse(hardware, ioctl=None, sleep=time.sleep):
    import fcntl
    ioctl = ioctl or fcntl.ioctl
    identity = hardware.discover()
    events = candidates(hardware, identity)
    if len(events) != 1:
        raise SuiteError('rumble_unavailable')
    event = Path(events[0])
    device_number = read_dev(event)
    node = None
    for directory in ('/dev/input', '/dev/inputplumber/sources'):
        p = Path(directory) / event.name
        try:
            st = p.stat()
            if stat.S_ISCHR(st.st_mode) and st.st_rdev == device_number:
                node = p
                break
        except OSError:
            continue
    if node is None:
        raise SuiteError('rumble_unavailable')
    fd = os.open(node, os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC)
    effect_id = None
    try:
        if os.fstat(fd).st_rdev != device_number or hardware.discover()['usb'] != identity['usb']:
            raise SuiteError('device_changed')
        if ctypes.sizeof(Effect) != 48:
            raise SuiteError('rumble_unavailable')
        effect = Effect(type=0x50, id=-1, length=500)
        effect.payload.rumble = Rumble(0xffff, 0xffff)
        buffer = bytearray(bytes(effect))
        ioctl(fd, 0x40304580, buffer, True)  # EVIOCSFF, 48-byte x86-64 ff_effect
        effect_id = Effect.from_buffer_copy(buffer).id
        if effect_id < 0:
            raise SuiteError('rumble_unavailable')
        os.write(fd, struct.pack('@llHHi', 0, 0, 0x15, effect_id, 1))
        sleep(0.55)  # Kernel replay length terminates it even if userspace exits.
    finally:
        try:
            if effect_id is not None:
                try:
                    os.write(fd, struct.pack('@llHHi', 0, 0, 0x15, effect_id, 0))
                finally:
                    ioctl(fd, 0x40044581, effect_id)  # EVIOCRMFF: only our effect
        finally:
            os.close(fd)


def read_dev(event):
    major, minor = Path(event, 'dev').read_text().strip().split(':')
    return os.makedev(int(major), int(minor))
