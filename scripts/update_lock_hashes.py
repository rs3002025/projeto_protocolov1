"""Generate integrity pins from official PyPI metadata; never changes versions."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def package_hashes(pin):
    name, version = pin.split('==')
    with urllib.request.urlopen(f'https://pypi.org/pypi/{name}/{version}/json', timeout=30) as response:
        metadata = json.load(response)
    hashes = sorted({item['digests']['sha256'] for item in metadata['urls']
                     if item['packagetype'] == 'bdist_wheel'})
    if not hashes:
        raise RuntimeError(f'No wheel available for {pin}; do not publish.')
    return pin + ' \\\n' + ' \\\n'.join('    --hash=sha256:' + digest for digest in hashes)


if __name__ == '__main__':
    pins = [line.strip() for line in (ROOT / 'requirements.lock').read_text().splitlines()
            if line.strip() and not line.startswith('#')]
    with ThreadPoolExecutor(max_workers=6) as executor:
        sections = list(executor.map(package_hashes, pins))
    (ROOT / 'requirements-hashes.lock').write_text(
        '# Generated from official PyPI wheel hashes. Versions: requirements.lock.\n'
        + '\n'.join(sections) + '\n', encoding='utf-8')
    print(f'Hashed {len(pins)} pinned packages.')
