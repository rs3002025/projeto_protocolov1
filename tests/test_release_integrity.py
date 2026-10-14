import base64
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_local_browser_assets_have_matching_integrity():
    manifest = json.loads((ROOT / 'static/vendor/manifest.json').read_text())
    assert len(manifest) == 6
    for name, info in manifest.items():
        data = (ROOT / 'static/vendor' / name).read_bytes()
        assert len(data) == info['bytes']
        assert hashlib.sha256(data).hexdigest() == info['sha256']
        assert 'sha384-' + base64.b64encode(hashlib.sha384(data).digest()).decode() == info['integrity']


def test_templates_no_longer_load_external_library_code():
    for path in (ROOT / 'templates').glob('*.html'):
        content = path.read_text(encoding='utf-8')
        assert 'https://cdn.jsdelivr.net' not in content
        assert 'https://cdnjs.cloudflare.com' not in content
    manifest = json.loads((ROOT / 'static/vendor/manifest.json').read_text())
    all_templates = ''.join(x.read_text(encoding='utf-8') for x in (ROOT / 'templates').glob('*.html'))
    for name, info in manifest.items():
        assert f'vendor/{name}' in all_templates
        assert info['integrity'] in all_templates


def test_container_uses_fixed_image_and_complete_lock():
    dockerfile = (ROOT / 'Dockerfile').read_text()
    assert 'python:3.12.15-slim@sha256:' in dockerfile
    assert '--require-hashes --only-binary=:all: --no-deps -r requirements-hashes.lock' in dockerfile
    assert 'python -m pip check' in dockerfile
    assert 'python scripts/verify_runtime.py' in dockerfile
    assert '-r requirements.lock' in (ROOT / 'requirements.txt').read_text()
    pins = [line for line in (ROOT / 'requirements.lock').read_text().splitlines()
            if line and not line.startswith('#')]
    assert len(pins) == 45
    assert all('==' in line and '>=' not in line for line in pins)
    hashed = (ROOT / 'requirements-hashes.lock').read_text()
    assert all(pin + ' \\' in hashed for pin in pins)
    assert '--hash=sha256:' in hashed


def test_runtime_verifier_fails_on_drift(monkeypatch):
    spec = importlib.util.spec_from_file_location('runtime_verifier', ROOT / 'scripts/verify_runtime.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    pins = dict(line.split('==') for line in (ROOT / 'requirements.lock').read_text().splitlines()
                if line and not line.startswith('#'))
    fake = [SimpleNamespace(metadata={'Name': name}, version=version) for name, version in pins.items()]
    monkeypatch.setattr(module.importlib.metadata, 'distributions', lambda: fake)
    monkeypatch.setattr(module.pip, '__version__', pins['pip'])
    assert len(module.verify_runtime()) == 64
    fake[0].version = '0.0.0'
    with pytest.raises(RuntimeError, match='mismatches'):
        module.verify_runtime()


def test_runtime_verifier_rejects_unexpected_package(monkeypatch):
    spec = importlib.util.spec_from_file_location('runtime_verifier_extra', ROOT / 'scripts/verify_runtime.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    pins = dict(line.split('==') for line in (ROOT / 'requirements.lock').read_text().splitlines()
                if line and not line.startswith('#'))
    fake = [SimpleNamespace(metadata={'Name': name}, version=version) for name, version in pins.items()]
    fake.append(SimpleNamespace(metadata={'Name': 'unexpected-lib'}, version='1.0'))
    monkeypatch.setattr(module.importlib.metadata, 'distributions', lambda: fake)
    monkeypatch.setattr(module.pip, '__version__', pins['pip'])
    with pytest.raises(RuntimeError, match='unexpected-lib'):
        module.verify_runtime()
