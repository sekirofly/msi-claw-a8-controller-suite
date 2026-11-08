"""Independent, versioned configurations. No cross-game live references."""
import copy
import json
import os
import re
from pathlib import Path


class SuiteError(Exception):
    pass


# UI labels are separate from InputPlumber's capability identifiers.
BUTTONS = {
    'M1': 'RightPaddle1', 'M2': 'LeftPaddle1', 'A': 'South', 'B': 'East',
    'X': 'North', 'Y': 'West', 'LB': 'LeftBumper', 'RB': 'RightBumper',
    'LS': 'LeftStick', 'RS': 'RightStick', 'Up': 'DPadUp', 'Down': 'DPadDown',
    'Left': 'DPadLeft', 'Right': 'DPadRight', 'Menu': 'Start', 'View': 'Select',
}
KEYS = ['KeySpace', 'KeyEnter', 'KeyEsc', 'KeyTab', 'KeyLeftShift', 'KeyLeftCtrl',
        'KeyLeftAlt'] + ['Key' + x for x in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789']
OUTPUTS = list(BUTTONS) + ['key:' + x for x in KEYS] + ['mouse:Left', 'mouse:Right', 'mouse:Middle']


def valid_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,20}', value) or int(value) == 0:
        raise SuiteError('invalid_game')
    return value


def validate_rules(rules):
    if not isinstance(rules, dict) or len(rules) > len(BUTTONS):
        raise SuiteError('invalid_rules')
    for source, targets in rules.items():
        if source not in BUTTONS or not isinstance(targets, list) or len(targets) > 4:
            raise SuiteError('invalid_rules')
        if any(not isinstance(t, str) or t not in OUTPUTS for t in targets) or len(set(targets)) != len(targets):
            raise SuiteError('invalid_rules')
    return copy.deepcopy(rules)


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    with temp.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.data = {'schema': 1, 'revision': 0, 'default': {}, 'games': {}, 'templates': {}}
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding='utf-8'))
                assert loaded['schema'] == 1 and type(loaded['revision']) is int
                validate_rules(loaded['default'])
                for key, entry in loaded['games'].items():
                    valid_id(key)
                    assert isinstance(entry['name'], str) and type(entry['enabled']) is bool
                    validate_rules(entry['rules'])
                for key, entry in loaded['templates'].items():
                    assert re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', key)
                    assert isinstance(entry['name'], str)
                    validate_rules(entry['rules'])
                self.data = loaded
            except Exception as exc:
                raise SuiteError('config_corrupt') from exc

    def snapshot(self):
        return copy.deepcopy(self.data)

    def save(self, scope, name, rules, enabled, revision):
        if revision != self.data['revision']:
            raise SuiteError('stale_edit')
        rules = validate_rules(rules)
        if not isinstance(name, str) or len(name) > 160 or type(enabled) is not bool:
            raise SuiteError('invalid_rules')
        next_data = self.snapshot()
        if scope == 'default':
            next_data['default'] = rules
        elif scope.startswith('template:'):
            key = scope[9:]
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', key):
                raise SuiteError('invalid_rules')
            next_data['templates'][key] = {'name': name, 'rules': rules}
        else:
            valid_id(scope)
            next_data['games'][scope] = {'name': name, 'enabled': enabled, 'rules': rules}
        self.commit(next_data)

    def delete(self, scope, revision):
        if revision != self.data['revision']:
            raise SuiteError('stale_edit')
        next_data = self.snapshot()
        if scope.startswith('template:'):
            next_data['templates'].pop(scope[9:], None)
        else:
            valid_id(scope)
            next_data['games'].pop(scope, None)
        self.commit(next_data)

    def commit(self, data):
        data['revision'] += 1
        atomic_json(self.path, data)
        self.data = data

    def selected(self, game):
        entry = self.data['games'].get(game)
        if entry and entry['enabled']:
            return game, copy.deepcopy(entry['rules'])
        return 'default', copy.deepcopy(self.data['default'])


def event(token):
    if token.startswith('key:'):
        return {'keyboard': token[4:]}
    if token.startswith('mouse:'):
        return {'mouse': {'button': token[6:]}}
    return {'gamepad': {'button': BUTTONS[token]}}


def compile_profile(base, rules):
    """Keep base behavior, but never import target-device changes from a profile."""
    rules = validate_rules(rules)
    result = copy.deepcopy(base)
    result.pop('target_devices', None)
    result['name'] = 'MSI Claw A8 Controller Suite'
    replaced = [event(source) for source in rules]
    result['mapping'] = [m for m in base.get('mapping', []) if m.get('source_event') not in replaced]
    result['mapping'] += [{'name': source, 'source_event': event(source),
                           'target_events': [event(t) for t in targets]}
                          for source, targets in rules.items()]
    return result
