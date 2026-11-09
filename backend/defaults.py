"""Read the installed InputPlumber defaults, never a captured live profile."""
from pathlib import Path
from .config import SuiteError

# InputPlumber's system data lookup uses /usr/local/share before /usr/share.
# Deliberately ignore /etc overrides from third-party management tools.
DATA_DIRS = (Path('/usr/local/share/inputplumber'), Path('/usr/share/inputplumber'))
DEVICE_FILE = '50-msi_claw_a8_bz2e.yaml'


def system_defaults():
    import yaml
    root = next((p for p in DATA_DIRS if p.is_dir()), DATA_DIRS[-1])
    try:
        profile = yaml.safe_load((root / 'profiles/default.yaml').read_text())
        device = yaml.safe_load((root / 'devices' / DEVICE_FILE).read_text())
        expected = {'board_name': 'MS-1T8K', 'board_vendor': 'Micro-Star International Co., Ltd.'}
        if (not isinstance(device, dict) or device.get('kind') != 'CompositeDevice'
                or {'dmi_data': expected} not in device.get('matches', [])):
            raise ValueError('Not the installed A8 device definition')
        if (not isinstance(profile, dict) or profile.get('kind') != 'DeviceProfile'
                or profile.get('version') != 1 or not isinstance(profile.get('mapping'), list)):
            raise ValueError('Invalid default profile')
        targets = profile.pop('target_devices', None) or device.get('target_devices')
        if (not isinstance(targets, list) or not targets
                or any(not isinstance(t, str) or not t for t in targets)
                or len(set(targets)) != len(targets)):
            raise ValueError('Invalid default targets')
        return profile, sorted(targets)
    except (OSError, ValueError, TypeError, yaml.YAMLError) as exc:
        raise SuiteError('system_defaults_unavailable') from exc
