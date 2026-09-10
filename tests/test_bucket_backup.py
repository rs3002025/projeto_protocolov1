import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

import pytest


SCRIPT = Path(__file__).parents[1] / 'scripts' / 'bucket_backup.py'
SPEC = importlib.util.spec_from_file_location('bucket_backup', SCRIPT)
bucket_backup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bucket_backup)


def make_archive(path, objects):
    manifest = {'format': 1, 'created_at': '2026-09-10T00:00:00+00:00',
                'source_bucket': 'teste', 'objects': []}
    with zipfile.ZipFile(path, 'w') as archive:
        for key, data in objects.items():
            entry = bucket_backup.object_entry_name(key)
            archive.writestr(entry, data)
            manifest['objects'].append({'key': key, 'entry': entry, 'size': len(data),
                                        'sha256': hashlib.sha256(data).hexdigest()})
        archive.writestr('manifest.json', json.dumps(manifest))
    return manifest


def test_manifesto_valida_objetos_e_chaves_nao_viram_caminhos(tmp_path):
    archive = tmp_path / 'bucket.zip'
    expected = make_archive(archive, {'tenants/1/../seguro.pdf': b'conteudo'})
    manifest = bucket_backup.validate_archive(archive)
    assert manifest == expected
    assert '..' not in manifest['objects'][0]['entry']


def test_validacao_detecta_conteudo_adulterado(tmp_path):
    archive = tmp_path / 'bucket.zip'
    make_archive(archive, {'arquivo.pdf': b'original'})
    with zipfile.ZipFile(archive, 'a') as output:
        output.writestr(bucket_backup.object_entry_name('arquivo.pdf'), b'adulterado')
    with pytest.raises(RuntimeError):
        bucket_backup.validate_archive(archive)


def test_diretorio_de_backup_nao_pode_ser_raiz():
    raiz = Path.cwd().anchor
    with pytest.raises(SystemExit):
        bucket_backup.safe_backup_directory(raiz)

