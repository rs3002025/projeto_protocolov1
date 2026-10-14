"""Fail a deployment whose effective Python dependencies differ from the lock."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import re
import pip


def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def verify_runtime():
    lock = Path(__file__).resolve().parents[1] / 'requirements.lock'
    expected = {}
    for line in lock.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            name, version = line.split('==', 1)
            expected[normalize(name)] = version
    effective = {normalize(d.metadata['Name']): d.version for d in importlib.metadata.distributions()
                 if d.metadata.get('Name')}
    # Older pip dist-info can coexist in the upstream image; check executed pip.
    effective['pip'] = pip.__version__
    mismatches = {name: {'expected': version, 'installed': effective.get(name)}
                  for name, version in expected.items() if effective.get(name) != version}
    unexpected = sorted(set(effective) - set(expected))
    if mismatches or unexpected:
        raise RuntimeError(json.dumps({'mismatches': mismatches, 'unexpected': unexpected}, sort_keys=True))
    fingerprint = hashlib.sha256(json.dumps(effective, sort_keys=True).encode()).hexdigest()
    print(json.dumps({'packages': len(effective), 'fingerprint': fingerprint, 'locked': True}))
    return fingerprint


if __name__ == '__main__':
    verify_runtime()
