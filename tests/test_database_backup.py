import hashlib
import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / 'scripts' / 'database_backup.py'
SPEC = importlib.util.spec_from_file_location('database_backup', SCRIPT)
database_backup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(database_backup)


def test_checksum_reflete_exatamente_o_conteudo(tmp_path):
    arquivo = tmp_path / 'backup.dump'
    arquivo.write_bytes(b'backup integral de teste')
    assert database_backup.sha256(arquivo) == hashlib.sha256(arquivo.read_bytes()).hexdigest()


def test_diretorio_de_backup_nao_pode_ser_raiz():
    raiz = Path.cwd().anchor
    with pytest.raises(SystemExit, match='pasta específica'):
        database_backup.safe_backup_directory(raiz)


def test_restauracao_exige_confirmacao_com_nome_exato(tmp_path, monkeypatch):
    arquivo = tmp_path / 'sysprot-teste.dump'
    arquivo.write_bytes(b'dump')
    monkeypatch.setenv('RESTORE_DATABASE_URL', 'postgresql://destino-de-teste')
    with pytest.raises(SystemExit, match='Confirmação inválida'):
        database_backup.restore(arquivo, 'RESTAURAR:outro.dump')


def test_executavel_pode_ser_localizado_por_postgres_bin(tmp_path, monkeypatch):
    executavel = tmp_path / ('pg_dump.exe' if database_backup.os.name == 'nt' else 'pg_dump')
    executavel.write_bytes(b'programa de teste')
    monkeypatch.setenv('POSTGRES_BIN', str(tmp_path))
    assert database_backup.executable('pg_dump') == str(executavel.resolve())
