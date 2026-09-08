"""Backup e restauração integral do PostgreSQL usado pelo Sysprot+.

O dump inclui esquema, dados, anexos e logos armazenados no banco. A restauração
é deliberadamente aceita apenas em banco vazio para evitar sobreposição acidental.
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone


def required_env(name):
    value = os.getenv(name, '').strip()
    if not value:
        raise SystemExit(f'A variável {name} é obrigatória.')
    return value


def safe_backup_directory(raw_path):
    directory = Path(raw_path).expanduser().resolve()
    if directory == Path(directory.anchor) or len(directory.parts) < 3:
        raise SystemExit('BACKUP_DIRECTORY deve apontar para uma pasta específica e persistente.')
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def executable(name):
    path = shutil.which(name)
    if not path:
        raise SystemExit(f'{name} não está instalado ou não está no PATH.')
    return path


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def run_checked(command):
    subprocess.run(command, check=True)


def backup(retention_days):
    database_url = required_env('DATABASE_URL')
    directory = safe_backup_directory(required_env('BACKUP_DIRECTORY'))
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    final_path = directory / f'sysprot-{timestamp}.dump'
    temporary_path = directory / f'.{final_path.name}.tmp'
    try:
        run_checked([executable('pg_dump'), '--format=custom', '--compress=9',
                     '--no-owner', '--no-privileges', '--file', str(temporary_path), database_url])
        run_checked([executable('pg_restore'), '--list', str(temporary_path)])
        temporary_path.replace(final_path)
        checksum = sha256(final_path)
        final_path.with_suffix('.dump.sha256').write_text(
            f'{checksum}  {final_path.name}\n', encoding='ascii')
    finally:
        temporary_path.unlink(missing_ok=True)

    cutoff = datetime.now(timezone.utc).timestamp() - retention_days * 86400
    for candidate in directory.glob('sysprot-*.dump'):
        if candidate != final_path and candidate.stat().st_mtime < cutoff:
            candidate.unlink()
            candidate.with_suffix('.dump.sha256').unlink(missing_ok=True)
    print(final_path)


def restore(backup_file, confirmation):
    database_url = required_env('RESTORE_DATABASE_URL')
    source = Path(backup_file).expanduser().resolve()
    if not source.is_file():
        raise SystemExit('Arquivo de backup não encontrado.')
    if confirmation != f'RESTAURAR:{source.name}':
        raise SystemExit(f'Confirmação inválida. Informe --confirm RESTAURAR:{source.name}')
    checksum_file = source.with_suffix('.dump.sha256')
    if not checksum_file.is_file() or checksum_file.read_text(encoding='ascii').split()[0] != sha256(source):
        raise SystemExit('Checksum ausente ou inválido; restauração cancelada.')
    run_checked([executable('pg_restore'), '--list', str(source)])
    query = "SELECT count(*) FROM pg_tables WHERE schemaname='public'"
    result = subprocess.run([executable('psql'), database_url, '-Atqc', query],
                            check=True, capture_output=True, text=True)
    if int(result.stdout.strip() or '0'):
        raise SystemExit('O banco de destino não está vazio; restauração cancelada.')
    run_checked([executable('pg_restore'), '--exit-on-error', '--no-owner', '--no-privileges',
                 '--dbname', database_url, str(source)])
    print('Restauração concluída em banco vazio e validada pelo pg_restore.')


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command', required=True)
    backup_parser = subparsers.add_parser('backup')
    backup_parser.add_argument('--retention-days', type=int, default=30)
    restore_parser = subparsers.add_parser('restore')
    restore_parser.add_argument('backup_file')
    restore_parser.add_argument('--confirm', required=True)
    args = parser.parse_args()
    if args.command == 'backup':
        if args.retention_days < 1:
            raise SystemExit('A retenção deve ser de pelo menos um dia.')
        backup(args.retention_days)
    else:
        restore(args.backup_file, args.confirm)


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(f'Ferramenta PostgreSQL encerrou com código {error.returncode}.', file=sys.stderr)
        raise SystemExit(error.returncode)
